import logging
from datetime import timedelta

from django.db import models
from django.utils import timezone
from netbox.jobs import JobRunner, system_job
from .models import PluginSettings

logger = logging.getLogger('netbox.netbox_ping')


class PrefixScanJob(JobRunner):
    """Background job to ping all existing IPs in a prefix."""

    class Meta:
        name = 'Prefix Scan'

    def run(self, data=None, **kwargs):
        from ipam.models import Prefix
        from .utils import scan_prefix

        prefix = Prefix.objects.get(pk=data['prefix_id'])
        settings = PluginSettings.load()

        self.logger.info(f'Starting scan of prefix {prefix.prefix}')
        result = scan_prefix(
            prefix,
            dns_servers=settings.get_dns_servers(),
            perform_dns=settings.perform_dns_lookup,
        )
        self.logger.info(f'Scan complete: {result["up"]}/{result["total"]} hosts up')


class PrefixDiscoverJob(JobRunner):
    """Background job to discover new IPs in a prefix."""

    class Meta:
        name = 'Prefix Discover'

    def run(self, data=None, **kwargs):
        from ipam.models import Prefix
        from .utils import discover_prefix

        prefix = Prefix.objects.get(pk=data['prefix_id'])
        settings = PluginSettings.load()

        self.logger.info(f'Starting discovery of prefix {prefix.prefix}')
        result = discover_prefix(
            prefix,
            dns_servers=settings.get_dns_servers(),
            perform_dns=settings.perform_dns_lookup,
        )
        self.logger.info(
            f'Discovery complete: found {len(result["discovered"])} new IPs '
            f'out of {result["total_scanned"]} scanned'
        )


class SingleIPPingJob(JobRunner):
    """Background job to ping a single IP address."""

    class Meta:
        name = 'Single IP Ping'

    def run(self, *args, **kwargs):
        from django.utils import timezone as tz
        from .utils import ping_host, resolve_dns
        from .models import PingResult, PingHistory

        ip_obj = self.job.object
        ip_str = str(ip_obj.address.ip)
        settings = PluginSettings.load()
        dns_servers = settings.get_dns_servers()

        self.logger.info(f'Pinging {ip_str}')

        ping_data = ping_host(ip_str)
        dns_name = ''
        if settings.perform_dns_lookup and ping_data['is_reachable']:
            dns_name = resolve_dns(ip_str, dns_servers)

        now = tz.now()
        existing_last_seen = None
        try:
            existing = PingResult.objects.get(ip_address=ip_obj)
            existing_last_seen = existing.last_seen
        except PingResult.DoesNotExist:
            pass

        PingResult.objects.update_or_create(
            ip_address=ip_obj,
            defaults={
                'is_reachable': ping_data['is_reachable'],
                'response_time_ms': ping_data['response_time_ms'],
                'dns_name': dns_name or (
                    PingResult.objects.filter(ip_address=ip_obj)
                    .values_list('dns_name', flat=True).first() or ''
                ),
                'last_checked': now,
                'last_seen': now if ping_data['is_reachable'] else existing_last_seen,
            },
        )
        PingHistory.objects.create(
            ip_address=ip_obj,
            is_reachable=ping_data['is_reachable'],
            response_time_ms=ping_data['response_time_ms'],
            dns_name=dns_name,
            checked_at=now,
        )

        status = 'up' if ping_data['is_reachable'] else 'down'
        self.logger.info(f'{ip_str} is {status}')


@system_job(interval=1)
class AutoScanDispatcherJob(JobRunner):
    """
    System job that runs every minute. Checks which prefixes are due
    for scanning or discovery and runs them directly.
    """

    class Meta:
        name = 'Auto-Scan Dispatcher'

    def run(self, *args, **kwargs):
        from ipam.models import Prefix
        from .models import PrefixSchedule, SubnetScanResult
        from .utils import scan_prefix, discover_prefix

        settings = PluginSettings.load()

        # Quick bail: nothing globally enabled and no custom_on overrides
        if not settings.auto_scan_enabled and not settings.auto_discover_enabled:
            if not PrefixSchedule.objects.filter(
                models.Q(scan_mode='custom_on') | models.Q(discover_mode='custom_on')
            ).exists():
                return

        now = timezone.now()
        dns_servers = settings.get_dns_servers()
        perform_dns = settings.perform_dns_lookup

        # Only consider prefixes at or smaller than the configured max size
        prefixes = Prefix.objects.filter(
            prefix__net_mask_length__gte=settings.max_prefix_size
        )

        # Bulk-load related data to avoid N+1 queries
        prefix_schedules = {
            ps.prefix_id: ps
            for ps in PrefixSchedule.objects.all()
        }
        scan_results = {
            sr.prefix_id: sr
            for sr in SubnetScanResult.objects.all()
        }

        scan_count = 0
        discover_count = 0

        for prefix in prefixes:
            schedule = prefix_schedules.get(prefix.pk)
            scan_result = scan_results.get(prefix.pk)
            last_scanned = scan_result.last_scanned if scan_result else None
            last_discovered = scan_result.last_discovered if scan_result else None

            # Determine effective settings for this prefix
            if schedule:
                scan_enabled = schedule.is_scan_enabled(settings)
                scan_interval = schedule.get_effective_scan_interval(settings)
                discover_enabled = schedule.is_discover_enabled(settings)
                discover_interval = schedule.get_effective_discover_interval(settings)
            else:
                # No per-prefix schedule → follow global
                scan_enabled = settings.auto_scan_enabled
                scan_interval = settings.auto_scan_interval
                discover_enabled = settings.auto_discover_enabled
                discover_interval = settings.auto_discover_interval

            # Run scan if due
            if scan_enabled and scan_interval > 0:
                if last_scanned is None or (now - last_scanned) >= timedelta(minutes=scan_interval):
                    try:
                        self.logger.info(f'Auto-scanning {prefix.prefix}')
                        scan_prefix(prefix, dns_servers=dns_servers, perform_dns=perform_dns)
                        scan_count += 1
                    except Exception as e:
                        self.logger.error(f'Auto-scan failed for {prefix.prefix}: {e}')

            # Run discover if due
            if discover_enabled and discover_interval > 0:
                if last_discovered is None or (now - last_discovered) >= timedelta(minutes=discover_interval):
                    try:
                        self.logger.info(f'Auto-discovering {prefix.prefix}')
                        discover_prefix(prefix, dns_servers=dns_servers, perform_dns=perform_dns)
                        discover_count += 1
                    except Exception as e:
                        self.logger.error(f'Auto-discover failed for {prefix.prefix}: {e}')

        if scan_count or discover_count:
            self.logger.info(
                f'Dispatcher completed: {scan_count} scan(s), {discover_count} discover(s)'
            )

        # Trim ping history to configured max
        from .models import PingHistory
        max_records = settings.ping_history_max_records
        if max_records > 0:
            total = PingHistory.objects.count()
            if total > max_records:
                cutoff_pk = PingHistory.objects.order_by('-checked_at').values_list(
                    'pk', flat=True
                )[max_records]
                PingHistory.objects.filter(pk__lt=cutoff_pk).delete()
