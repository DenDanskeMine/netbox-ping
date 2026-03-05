import logging
from datetime import timedelta

from django.utils import timezone
from netbox.jobs import JobRunner, system_job
from .models import PluginSettings

logger = logging.getLogger('netbox.netbox_ping')


def _schedule_next_scan(prefix, settings):
    """
    Compute and store next_scan_at for a prefix, then enqueue a scheduled job.
    Safe to call after any scan (manual or auto) so the countdown always resets.

    Uses SubnetScanResult.scan_job_id to track the scheduled job PK instead of
    instance=prefix (Prefix is not a JobsMixin model, so NetBox rejects instance-
    linked jobs for it).
    """
    from .models import PrefixSchedule, SubnetScanResult
    from core.models import Job as CoreJob

    schedule = PrefixSchedule.objects.filter(prefix=prefix).first()
    if schedule:
        enabled = schedule.is_scan_enabled(settings)
        interval = schedule.get_effective_scan_interval(settings)
    else:
        enabled = settings.auto_scan_enabled
        interval = settings.auto_scan_interval

    ssr, _ = SubnetScanResult.objects.get_or_create(prefix=prefix)

    if enabled and interval > 0:
        next_at = timezone.now() + timedelta(minutes=interval)

        # Cancel the previously scheduled job if still pending/scheduled
        if ssr.scan_job_id:
            CoreJob.objects.filter(pk=ssr.scan_job_id, status__in=['pending', 'scheduled']).delete()

        job = PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
        ssr.next_scan_at = next_at
        ssr.scan_job_id = job.pk
        ssr.save(update_fields=['next_scan_at', 'scan_job_id'])
        logger.debug(f'Scheduled next scan of {prefix.prefix} at {next_at}')
    else:
        # Auto-scan disabled — cancel existing job and clear timestamps
        if ssr.scan_job_id:
            CoreJob.objects.filter(pk=ssr.scan_job_id, status__in=['pending', 'scheduled']).delete()
        ssr.next_scan_at = None
        ssr.scan_job_id = None
        ssr.save(update_fields=['next_scan_at', 'scan_job_id'])


def _schedule_next_discover(prefix, settings):
    """
    Compute and store next_discover_at for a prefix, then enqueue a scheduled job.
    Uses SubnetScanResult.discover_job_id for deduplication (same reason as scan).
    """
    from .models import PrefixSchedule, SubnetScanResult
    from core.models import Job as CoreJob

    schedule = PrefixSchedule.objects.filter(prefix=prefix).first()
    if schedule:
        enabled = schedule.is_discover_enabled(settings)
        interval = schedule.get_effective_discover_interval(settings)
    else:
        enabled = settings.auto_discover_enabled
        interval = settings.auto_discover_interval

    ssr, _ = SubnetScanResult.objects.get_or_create(prefix=prefix)

    if enabled and interval > 0:
        next_at = timezone.now() + timedelta(minutes=interval)

        if ssr.discover_job_id:
            CoreJob.objects.filter(pk=ssr.discover_job_id, status__in=['pending', 'scheduled']).delete()

        job = PrefixDiscoverJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
        ssr.next_discover_at = next_at
        ssr.discover_job_id = job.pk
        ssr.save(update_fields=['next_discover_at', 'discover_job_id'])
        logger.debug(f'Scheduled next discover of {prefix.prefix} at {next_at}')
    else:
        if ssr.discover_job_id:
            CoreJob.objects.filter(pk=ssr.discover_job_id, status__in=['pending', 'scheduled']).delete()
        ssr.next_discover_at = None
        ssr.discover_job_id = None
        ssr.save(update_fields=['next_discover_at', 'discover_job_id'])


def _schedule_next_digest(settings):
    """
    Compute next_digest_at and enqueue an EmailDigestJob if email is enabled.
    Cancels any existing scheduled digest job if email is disabled.
    """
    if not settings.email_notifications_enabled or settings.email_digest_interval <= 0:
        settings.next_digest_at = None
        settings.save(update_fields=['next_digest_at'])
        _cancel_scheduled_digest_jobs()
        return

    next_at = timezone.now() + timedelta(minutes=settings.email_digest_interval)
    settings.next_digest_at = next_at
    settings.save(update_fields=['next_digest_at'])
    EmailDigestJob.enqueue_once(schedule_at=next_at)
    logger.debug(f'Scheduled next email digest at {next_at}')


def _cancel_scheduled_digest_jobs():
    """Cancel any pending/scheduled EmailDigestJob entries."""
    try:
        EmailDigestJob.get_jobs().filter(
            status__in=['pending', 'scheduled']
        ).delete()
    except Exception:
        pass


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

        # Schedule the next scan (resets countdown whether triggered manually or auto)
        _schedule_next_scan(prefix, settings)


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

        # Schedule the next discovery
        _schedule_next_discover(prefix, settings)


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


@system_job(interval=1440)
class ScheduleRecoveryJob(JobRunner):
    """
    Runs daily. Lightweight recovery job that re-enqueues any scheduled
    scans/discoveries that were lost (e.g. Redis restart without persistence).
    Also bootstraps scheduling for newly enabled prefixes.

    Under normal operation this does very little — the real scheduling is
    driven by PrefixScanJob/PrefixDiscoverJob self-rescheduling at the end
    of each run, and by Django signals when settings change.
    On every netbox-rq startup, enqueue_once already runs recovery for free.
    """

    class Meta:
        name = 'Schedule Recovery'

    def run(self, *args, **kwargs):
        from ipam.models import Prefix
        from .models import PrefixSchedule, SubnetScanResult
        from core.models import Job as CoreJob

        settings = PluginSettings.load()
        now = timezone.now()

        prefix_schedules = {
            ps.prefix_id: ps
            for ps in PrefixSchedule.objects.all()
        }
        scan_results = {
            sr.prefix_id: sr
            for sr in SubnetScanResult.objects.all()
        }

        # Only consider prefixes at or smaller than the configured max size
        prefixes = list(Prefix.objects.filter(
            prefix__net_mask_length__gte=settings.max_prefix_size
        ))

        recovered_scan = 0
        recovered_discover = 0
        bootstrapped_scan = 0
        bootstrapped_discover = 0

        for prefix in prefixes:
            schedule = prefix_schedules.get(prefix.pk)
            ssr = scan_results.get(prefix.pk)

            # --- Effective settings for this prefix ---
            if schedule:
                scan_enabled = schedule.is_scan_enabled(settings)
                scan_interval = schedule.get_effective_scan_interval(settings)
                discover_enabled = schedule.is_discover_enabled(settings)
                discover_interval = schedule.get_effective_discover_interval(settings)
            else:
                scan_enabled = settings.auto_scan_enabled
                scan_interval = settings.auto_scan_interval
                discover_enabled = settings.auto_discover_enabled
                discover_interval = settings.auto_discover_interval

            # --- Helpers: check active jobs via stored PK (Prefix is not a
            #     JobsMixin model, so instance-linked jobs are not supported) ---
            def _has_active_scan(statuses):
                if ssr and ssr.scan_job_id:
                    return CoreJob.objects.filter(pk=ssr.scan_job_id, status__in=statuses).exists()
                return False

            def _has_active_discover(statuses):
                if ssr and ssr.discover_job_id:
                    return CoreJob.objects.filter(pk=ssr.discover_job_id, status__in=statuses).exists()
                return False

            # --- Scan recovery / bootstrap ---
            if scan_enabled and scan_interval > 0:
                if ssr and ssr.next_scan_at:
                    if ssr.next_scan_at <= now:
                        # Overdue — re-enqueue immediately if no active job
                        if not _has_active_scan(['pending', 'scheduled', 'running']):
                            job = PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=now)
                            ssr.scan_job_id = job.pk
                            ssr.save(update_fields=['scan_job_id'])
                            recovered_scan += 1
                    else:
                        # Future — re-enqueue if job was lost (e.g. Redis wipe)
                        if not _has_active_scan(['pending', 'scheduled']):
                            job = PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=ssr.next_scan_at)
                            ssr.scan_job_id = job.pk
                            ssr.save(update_fields=['scan_job_id'])
                            recovered_scan += 1
                else:
                    # No next_scan_at yet — bootstrap for newly enabled prefixes
                    if not _has_active_scan(['pending', 'scheduled', 'running']):
                        next_at = now + timedelta(minutes=scan_interval)
                        if ssr:
                            ssr.next_scan_at = next_at
                            job = PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
                            ssr.scan_job_id = job.pk
                            ssr.save(update_fields=['next_scan_at', 'scan_job_id'])
                        else:
                            job = PrefixScanJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
                            ssr = SubnetScanResult.objects.create(
                                prefix=prefix, next_scan_at=next_at, scan_job_id=job.pk
                            )
                            scan_results[prefix.pk] = ssr
                        bootstrapped_scan += 1

            # --- Discover recovery / bootstrap ---
            if discover_enabled and discover_interval > 0:
                if ssr and ssr.next_discover_at:
                    if ssr.next_discover_at <= now:
                        if not _has_active_discover(['pending', 'scheduled', 'running']):
                            job = PrefixDiscoverJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=now)
                            ssr.discover_job_id = job.pk
                            ssr.save(update_fields=['discover_job_id'])
                            recovered_discover += 1
                    else:
                        if not _has_active_discover(['pending', 'scheduled']):
                            job = PrefixDiscoverJob.enqueue(
                                data={'prefix_id': prefix.pk}, schedule_at=ssr.next_discover_at
                            )
                            ssr.discover_job_id = job.pk
                            ssr.save(update_fields=['discover_job_id'])
                            recovered_discover += 1
                else:
                    if not _has_active_discover(['pending', 'scheduled', 'running']):
                        next_at = now + timedelta(minutes=discover_interval)
                        if ssr:
                            ssr.next_discover_at = next_at
                            job = PrefixDiscoverJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
                            ssr.discover_job_id = job.pk
                            ssr.save(update_fields=['next_discover_at', 'discover_job_id'])
                        else:
                            ssr = SubnetScanResult.objects.get_or_create(prefix=prefix)[0]
                            ssr.next_discover_at = next_at
                            job = PrefixDiscoverJob.enqueue(data={'prefix_id': prefix.pk}, schedule_at=next_at)
                            ssr.discover_job_id = job.pk
                            ssr.save(update_fields=['next_discover_at', 'discover_job_id'])
                            scan_results[prefix.pk] = ssr
                        bootstrapped_discover += 1

        # --- Email digest recovery ---
        if settings.email_notifications_enabled and settings.email_digest_interval > 0:
            if settings.next_digest_at:
                has_active = EmailDigestJob.get_jobs().filter(
                    status__in=['pending', 'scheduled']
                ).exists()
                if not has_active:
                    run_at = settings.next_digest_at if settings.next_digest_at > now else now
                    EmailDigestJob.enqueue_once(schedule_at=run_at)

        # --- Housekeeping ---
        from .models import PingHistory
        max_records = settings.ping_history_max_records
        if max_records > 0:
            total = PingHistory.objects.count()
            if total > max_records:
                to_delete = total - max_records
                print(f'[Recovery] Trimming {to_delete} old history records', flush=True)
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
                print(f'[Recovery] Trimmed {deleted} history records', flush=True)

        from .models import ScanEvent, PingResult as PingResultModel
        cutoff = now - timedelta(days=7)
        pruned = ScanEvent.objects.filter(created_at__lt=cutoff).delete()[0]
        if pruned:
            print(f'[Recovery] Pruned {pruned} old scan event(s)', flush=True)

        new_days = settings.new_ip_days_threshold
        if new_days > 0:
            expiry_cutoff = now - timedelta(days=new_days)
            expired_new = PingResultModel.objects.filter(
                is_new=True, discovered_at__lt=expiry_cutoff,
            ).update(is_new=False)
            if expired_new:
                print(f'[Recovery] Expired "New" badge on {expired_new} IP(s)', flush=True)
        elif new_days == 0:
            cleared = PingResultModel.objects.filter(is_new=True).update(is_new=False)
            if cleared:
                print(f'[Recovery] Cleared {cleared} "New" badge(s) (feature disabled)', flush=True)

        total_recovered = recovered_scan + recovered_discover
        total_bootstrapped = bootstrapped_scan + bootstrapped_discover
        if total_recovered or total_bootstrapped:
            msg = (
                f'Recovered {recovered_scan} scan / {recovered_discover} discover job(s); '
                f'bootstrapped {bootstrapped_scan} scan / {bootstrapped_discover} discover job(s)'
            )
            self.logger.info(msg)
            print(f'[Recovery] {msg}', flush=True)

        print('[Recovery] Done', flush=True)


class EmailDigestJob(JobRunner):
    """
    Sends a summary email digest. Self-schedules the next run on completion.
    Only exists in the job list when email notifications are enabled.
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

        # Gate 3: interval > 0?
        interval = settings.email_digest_interval
        if interval <= 0:
            return

        now = timezone.now()
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
            settings.email_last_digest_sent = now
            settings.save(update_fields=['email_last_digest_sent'])
            _schedule_next_digest(settings)
            return

        # Build and send email
        subject, html_body, text_body = build_digest_email(
            events, high_util, settings.email_include_details,
            period_start, period_end, threshold,
        )

        try:
            from django.conf import settings as django_settings
            from_email = (
                getattr(django_settings, 'SERVER_EMAIL', None)
                or getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'netbox@localhost')
            )
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

            if events:
                event_ids = [e.pk for e in events]
                ScanEvent.objects.filter(pk__in=event_ids).update(digest_sent=True)

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
        finally:
            # Always schedule the next digest (even on failure) so it doesn't stall
            _schedule_next_digest(settings)
