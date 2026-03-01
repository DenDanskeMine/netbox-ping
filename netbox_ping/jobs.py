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
        print(f'[Prefix Scan] Starting scan of {prefix.prefix}', flush=True)
        result = scan_prefix(
            prefix,
            dns_servers=settings.get_dns_servers(),
            perform_dns=settings.perform_dns_lookup,
            max_workers=settings.ping_concurrency,
            ping_timeout=settings.ping_timeout,
            dns_settings=settings,
            job_logger=self.logger,
            skip_reserved=settings.skip_reserved_ips,
        )
        skipped_str = f', {result["skipped"]} skipped' if result.get('skipped') else ''
        self.logger.info(f'Scan complete: {result["up"]}/{result["total"]} hosts up{skipped_str}')
        print(f'[Prefix Scan] Complete: {result["up"]}/{result["total"]} hosts up{skipped_str}', flush=True)


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
        print(f'[Prefix Discover] Starting discovery of {prefix.prefix}', flush=True)
        result = discover_prefix(
            prefix,
            dns_servers=settings.get_dns_servers(),
            perform_dns=settings.perform_dns_lookup,
            max_workers=settings.ping_concurrency,
            ping_timeout=settings.ping_timeout,
            dns_settings=settings,
            job_logger=self.logger,
        )
        self.logger.info(
            f'Discovery complete: found {len(result["discovered"])} new IPs '
            f'out of {result["total_scanned"]} scanned'
        )
        print(
            f'[Prefix Discover] Complete: {len(result["discovered"])} new IPs '
            f'out of {result["total_scanned"]} scanned', flush=True
        )


class SingleIPPingJob(JobRunner):
    """Background job to ping a single IP address."""

    class Meta:
        name = 'Single IP Ping'

    def run(self, *args, **kwargs):
        from django.utils import timezone as tz
        from .utils import ping_host, resolve_dns, _compute_dns_sync
        from .models import PingResult, PingHistory, DnsHistory, ScanEvent

        ip_obj = self.job.object
        ip_str = str(ip_obj.address.ip)
        settings = PluginSettings.load()
        dns_servers = settings.get_dns_servers()

        self.logger.info(f'Pinging {ip_str}')

        ping_data = ping_host(ip_str)
        dns_name = ''
        dns_attempted = False
        if settings.perform_dns_lookup and ping_data['is_reachable']:
            dns_attempted = True
            dns_name = resolve_dns(ip_str, dns_servers)

        now = tz.now()
        existing_last_seen = None
        try:
            existing = PingResult.objects.get(ip_address=ip_obj)
            existing_last_seen = existing.last_seen
            # Detect state changes for digest events
            if not existing.is_skipped:
                if existing.is_reachable and not ping_data['is_reachable']:
                    ScanEvent.objects.create(
                        event_type='ip_went_down',
                        ip_address=ip_obj,
                        detail={
                            'dns_name': existing.dns_name or '',
                            'last_response_ms': existing.response_time_ms,
                        },
                    )
                elif not existing.is_reachable and ping_data['is_reachable']:
                    ScanEvent.objects.create(
                        event_type='ip_came_up',
                        ip_address=ip_obj,
                        detail={
                            'dns_name': dns_name or existing.dns_name or '',
                            'response_time_ms': ping_data['response_time_ms'],
                        },
                    )
        except PingResult.DoesNotExist:
            pass

        PingResult.objects.update_or_create(
            ip_address=ip_obj,
            defaults={
                'is_reachable': ping_data['is_reachable'],
                'is_skipped': False,
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

        # DNS sync
        if settings.dns_sync_to_netbox:
            current_netbox_dns = ip_obj.dns_name or ''
            should_update, new_value = _compute_dns_sync(
                dns_name, ping_data['is_reachable'], dns_attempted,
                current_netbox_dns, settings,
            )
            if should_update:
                ip_obj.dns_name = new_value
                ip_obj.save(update_fields=['dns_name'])
                DnsHistory.objects.create(
                    ip_address=ip_obj,
                    old_dns_name=current_netbox_dns,
                    new_dns_name=new_value,
                    changed_at=now,
                )
                ScanEvent.objects.create(
                    event_type='dns_changed',
                    ip_address=ip_obj,
                    detail={
                        'old_dns': current_netbox_dns,
                        'new_dns': new_value,
                    },
                )

        status = 'up' if ping_data['is_reachable'] else 'down'
        self.logger.info(f'{ip_str} is {status}')


@system_job(interval=1)
class AutoScanDispatcherJob(JobRunner):
    """
    System job that runs every minute. Checks which prefixes are due
    for scanning or discovery and enqueues background jobs for them.
    """

    class Meta:
        name = 'Auto-Scan Dispatcher'

    def run(self, *args, **kwargs):
        from ipam.models import Prefix
        from .models import PrefixSchedule, SubnetScanResult

        settings = PluginSettings.load()

        # Quick bail: nothing globally enabled and no custom_on overrides
        if not settings.auto_scan_enabled and not settings.auto_discover_enabled:
            if not PrefixSchedule.objects.filter(
                models.Q(scan_mode='custom_on') | models.Q(discover_mode='custom_on')
            ).exists():
                return

        now = timezone.now()

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

            # Enqueue scan job if due
            if scan_enabled and scan_interval > 0:
                if last_scanned is None or (now - last_scanned) >= timedelta(minutes=scan_interval):
                    try:
                        self.logger.info(f'Enqueuing auto-scan for {prefix.prefix}')
                        PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, job_timeout=1800)
                        scan_count += 1
                    except Exception as e:
                        self.logger.error(f'Failed to enqueue auto-scan for {prefix.prefix}: {e}')

            # Enqueue discover job if due
            if discover_enabled and discover_interval > 0:
                if last_discovered is None or (now - last_discovered) >= timedelta(minutes=discover_interval):
                    try:
                        self.logger.info(f'Enqueuing auto-discover for {prefix.prefix}')
                        PrefixDiscoverJob.enqueue(data={'prefix_id': prefix.pk}, job_timeout=1800)
                        discover_count += 1
                    except Exception as e:
                        self.logger.error(f'Failed to enqueue auto-discover for {prefix.prefix}: {e}')

        if scan_count or discover_count:
            msg = f'Dispatcher enqueued {scan_count} scan(s), {discover_count} discover(s)'
            self.logger.info(msg)
            print(f'[Dispatcher] {msg}', flush=True)
        else:
            print('[Dispatcher] No prefixes due for scanning', flush=True)

        # Trim ping history to configured max (raw SQL to avoid ORM overhead)
        from .models import PingHistory
        max_records = settings.ping_history_max_records
        if max_records > 0:
            total = PingHistory.objects.count()
            if total > max_records:
                to_delete = total - max_records
                print(f'[Dispatcher] Trimming {to_delete} old history records', flush=True)
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM netbox_ping_pinghistory
                        WHERE id NOT IN (
                            SELECT id FROM netbox_ping_pinghistory
                            ORDER BY checked_at DESC
                            LIMIT %s
                        )
                    """, [max_records])
                    deleted = cursor.rowcount
                print(f'[Dispatcher] Trimmed {deleted} history records', flush=True)

        # Prune old ScanEvent records (older than 7 days)
        from .models import ScanEvent, PingResult as PingResultModel
        cutoff = now - timedelta(days=7)
        pruned = ScanEvent.objects.filter(created_at__lt=cutoff).delete()[0]
        if pruned:
            print(f'[Dispatcher] Pruned {pruned} old scan event(s)', flush=True)

        # Expire "New" badges
        new_days = settings.new_ip_days_threshold
        if new_days > 0:
            expiry_cutoff = now - timedelta(days=new_days)
            expired_new = PingResultModel.objects.filter(
                is_new=True, discovered_at__lt=expiry_cutoff,
            ).update(is_new=False)
            if expired_new:
                print(f'[Dispatcher] Expired "New" badge on {expired_new} IP(s)', flush=True)
        elif new_days == 0:
            cleared = PingResultModel.objects.filter(is_new=True).update(is_new=False)
            if cleared:
                print(f'[Dispatcher] Cleared {cleared} "New" badge(s) (feature disabled)', flush=True)

        print('[Dispatcher] Done', flush=True)


@system_job(interval=60)
class EmailDigestJob(JobRunner):
    """
    System job that runs every hour. Checks if a digest email is due
    based on the configured interval, collects unsent ScanEvents,
    and sends a summary email.
    """

    class Meta:
        name = 'Email Digest'

    def run(self, *args, **kwargs):
        from django.core.mail import send_mail
        from .models import ScanEvent, SubnetScanResult
        from .email import build_digest_email

        settings = PluginSettings.load()

        # Gate 1: notifications enabled?
        if not settings.email_notifications_enabled:
            return

        # Gate 2: any recipients?
        raw_recipients = settings.email_recipients.strip()
        if not raw_recipients:
            return
        recipients = [r.strip() for r in raw_recipients.split(',') if r.strip()]
        if not recipients:
            return

        # Gate 3: interval > 0 and time elapsed?
        interval = settings.email_digest_interval
        if interval <= 0:
            return

        now = timezone.now()
        if settings.email_last_digest_sent:
            next_due = settings.email_last_digest_sent + timedelta(minutes=interval)
            if now < next_due:
                return

        period_start = settings.email_last_digest_sent or (now - timedelta(minutes=interval))
        period_end = now

        # Collect unsent events
        events = list(
            ScanEvent.objects.filter(digest_sent=False)
            .select_related('ip_address', 'prefix')
            .order_by('created_at')
        )

        # Collect high-utilization prefixes
        high_util = []
        threshold = settings.email_utilization_threshold
        if threshold > 0:
            for ssr in SubnetScanResult.objects.select_related('prefix').all():
                if ssr.total_hosts > 0 and ssr.utilization >= threshold:
                    high_util.append(ssr)

        # Gate 4: skip if no changes and on_change_only
        if settings.email_on_change_only and not events and not high_util:
            # Still update timestamp so we don't re-check old window
            settings.email_last_digest_sent = now
            settings.save(update_fields=['email_last_digest_sent'])
            return

        # Build email
        subject, html_body, text_body = build_digest_email(
            events, high_util, settings.email_include_details,
            period_start, period_end, threshold,
        )

        # Send
        try:
            from django.conf import settings as django_settings
            from_email = getattr(django_settings, 'SERVER_EMAIL', None) or getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'netbox@localhost')
            send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=recipients,
                html_message=html_body,
                fail_silently=False,
            )
            msg = f'Digest email sent to {len(recipients)} recipient(s) ({len(events)} events)'
            self.logger.info(msg)
            print(f'[Email Digest] {msg}', flush=True)

            # Mark events as sent
            if events:
                event_ids = [e.pk for e in events]
                ScanEvent.objects.filter(pk__in=event_ids).update(digest_sent=True)

            # Update timestamp
            settings.email_last_digest_sent = now
            settings.save(update_fields=['email_last_digest_sent'])

            # Prune sent events older than 7 days
            cutoff = now - timedelta(days=7)
            pruned = ScanEvent.objects.filter(digest_sent=True, created_at__lt=cutoff).delete()[0]
            if pruned:
                print(f'[Email Digest] Pruned {pruned} old sent event(s)', flush=True)

        except Exception as e:
            self.logger.error(f'Failed to send digest email: {e}')
            print(f'[Email Digest] ERROR: {e}', flush=True)
