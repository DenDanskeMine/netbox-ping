import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from ipam.models import Prefix, IPAddress

from .models import (
    PingResult, PingHistory, SubnetScanResult, PluginSettings,
    PrefixSchedule, DnsHistory, SSHJumpHost, UptimeReset,
)
from .tables import PingResultTable, PingHistoryTable, SubnetScanResultTable, DnsHistoryTable
from .filtersets import PingResultFilterSet, PingHistoryFilterSet, SubnetScanResultFilterSet
from .forms import PingResultFilterForm, PingHistoryFilterForm, SubnetScanResultFilterForm, PluginSettingsForm, PrefixScheduleForm, SSHJumpHostForm

logger = logging.getLogger('netbox.netbox_ping')


# ─── PingResult CRUD Views ─────────────────────────────────────

class PingResultListView(generic.ObjectListView):
    queryset = PingResult.objects.select_related('ip_address')
    table = PingResultTable
    filterset = PingResultFilterSet
    filterset_form = PingResultFilterForm
    template_name = 'netbox_ping/pingresult_list.html'
    actions = {
        'export': set(),
        'bulk_delete': {'delete'},
    }


class PingResultView(generic.ObjectView):
    queryset = PingResult.objects.select_related('ip_address')


class PingResultDeleteView(generic.ObjectDeleteView):
    queryset = PingResult.objects.all()


class PingResultBulkDeleteView(generic.BulkDeleteView):
    queryset = PingResult.objects.all()
    filterset = PingResultFilterSet
    table = PingResultTable


# ─── PingHistory CRUD Views ────────────────────────────────────

class PingHistoryListView(generic.ObjectListView):
    queryset = PingHistory.objects.select_related('ip_address')
    table = PingHistoryTable
    filterset = PingHistoryFilterSet
    filterset_form = PingHistoryFilterForm
    actions = {
        'export': set(),
        'bulk_delete': {'delete'},
    }


class PingHistoryView(generic.ObjectView):
    queryset = PingHistory.objects.select_related('ip_address')


class PingHistoryDeleteView(generic.ObjectDeleteView):
    queryset = PingHistory.objects.all()


class PingHistoryBulkDeleteView(generic.BulkDeleteView):
    queryset = PingHistory.objects.all()
    filterset = PingHistoryFilterSet
    table = PingHistoryTable


# ─── SubnetScanResult CRUD Views ───────────────────────────────

class SubnetScanResultListView(generic.ObjectListView):
    queryset = SubnetScanResult.objects.select_related('prefix')
    table = SubnetScanResultTable
    filterset = SubnetScanResultFilterSet
    filterset_form = SubnetScanResultFilterForm
    actions = {
        'export': set(),
        'bulk_delete': {'delete'},
    }


class SubnetScanResultView(generic.ObjectView):
    queryset = SubnetScanResult.objects.select_related('prefix')


class SubnetScanResultDeleteView(generic.ObjectDeleteView):
    queryset = SubnetScanResult.objects.all()


# ─── Extra Tabs on Core Models ─────────────────────────────────

@register_model_view(Prefix, 'ping', path='ping')
class PrefixPingTab(generic.ObjectChildrenView):
    """Tab on Prefix detail page showing ping results for child IPs."""

    queryset = Prefix.objects.all()
    child_model = PingResult
    table = PingResultTable
    template_name = 'netbox_ping/prefix_ping_tab.html'
    tab = ViewTab(
        label='Ping Status',
        badge=lambda obj: PingResult.objects.filter(
            ip_address__in=obj.get_child_ips()
        ).count() or None,
        permission='netbox_ping.view_pingresult',
        weight=1500,
    )

    def get_children(self, request, parent):
        return PingResult.objects.filter(
            ip_address__in=parent.get_child_ips()
        ).select_related('ip_address')

    def get_extra_context(self, request, instance):
        try:
            schedule = PrefixSchedule.objects.get(prefix=instance)
        except PrefixSchedule.DoesNotExist:
            schedule = None
        plugin_settings = PluginSettings.load()
        schedule_form = PrefixScheduleForm(instance=schedule)
        try:
            scan_result = SubnetScanResult.objects.get(prefix=instance)
        except SubnetScanResult.DoesNotExist:
            scan_result = None
        return {
            'schedule': schedule,
            'schedule_form': schedule_form,
            'plugin_settings': plugin_settings,
            'scan_result': scan_result,
        }


@register_model_view(IPAddress, 'ping', path='ping')
class IPAddressPingTab(generic.ObjectView):
    """Tab on IPAddress detail page showing ping status."""

    queryset = IPAddress.objects.all()
    template_name = 'netbox_ping/ipaddress_ping_tab.html'
    tab = ViewTab(
        label='Ping Status',
        permission='netbox_ping.view_pingresult',
        weight=1500,
    )

    def get_extra_context(self, request, instance):
        try:
            ping_result = PingResult.objects.get(ip_address=instance)
        except PingResult.DoesNotExist:
            ping_result = None
        history = PingHistory.objects.filter(ip_address=instance).select_related('ip_address')[:50]
        history_table = PingHistoryTable(history, orderable=False)
        dns_history = DnsHistory.objects.filter(ip_address=instance)[:50]
        dns_history_table = DnsHistoryTable(dns_history, orderable=False)

        # Uptime / SLA stats
        ctx = {
            'ping_result': ping_result,
            'history_table': history_table,
            'dns_history_table': dns_history_table,
        }
        if ping_result:
            windows = [('24h', 24), ('7d', 24 * 7), ('30d', 24 * 30), ('all_time', None)]
            for label, hours in windows:
                stats = ping_result.uptime_percentage(hours=hours)
                if stats:
                    ctx[f'uptime_{label}'] = stats['percentage']
                    ctx[f'uptime_{label}_up'] = stats['up']
                    ctx[f'uptime_{label}_total'] = stats['total']
                    ctx[f'uptime_{label}_color'] = ping_result.uptime_color(stats['percentage'])
                else:
                    ctx[f'uptime_{label}'] = None
                    ctx[f'uptime_{label}_color'] = 'secondary'
            # Last reset event (for banner)
            ctx['last_reset'] = ping_result.last_reset
            # Full reset history (shown in collapsible section)
            ctx['reset_history'] = UptimeReset.objects.filter(
                ip_address=instance,
            ).select_related('reset_by').order_by('-reset_at')[:20]
        return ctx


# ─── Action Views (trigger scans) ──────────────────────────────

class PrefixScanActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Triggers a scan of all existing IPs in a prefix."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        from .jobs import PrefixScanJob, _label_job

        prefix = get_object_or_404(Prefix, pk=pk)
        job = PrefixScanJob.enqueue(user=request.user, data={'prefix_id': prefix.pk, 'manual': True}, job_timeout=1800)
        _label_job(job, f'Prefix Scan: {prefix.prefix}')
        messages.info(request, f'Scan job enqueued for {prefix.prefix}')
        return redirect(prefix.get_absolute_url() + 'ping/')


class PrefixDiscoverActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Triggers discovery of new IPs in a prefix."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        from .jobs import PrefixDiscoverJob, _label_job

        prefix = get_object_or_404(Prefix, pk=pk)
        job = PrefixDiscoverJob.enqueue(user=request.user, data={'prefix_id': prefix.pk, 'manual': True}, job_timeout=1800)
        _label_job(job, f'Prefix Discover: {prefix.prefix}')
        messages.info(request, f'Discover job enqueued for {prefix.prefix}')
        return redirect(prefix.get_absolute_url() + 'ping/')


class BulkPrefixScanView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Scans selected prefixes (or all if none selected)."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request):
        from .jobs import PrefixScanJob

        pks = request.GET.getlist('pk')
        if pks:
            prefixes = Prefix.objects.filter(pk__in=pks)
        else:
            prefixes = Prefix.objects.all()

        count = 0
        for prefix in prefixes:
            from .jobs import PrefixScanJob, _label_job
            job = PrefixScanJob.enqueue(user=request.user, data={'prefix_id': prefix.pk, 'manual': True}, job_timeout=1800)
            _label_job(job, f'Prefix Scan: {prefix.prefix}')
            count += 1

        messages.info(
            request,
            f'Enqueued scan jobs for {count} prefixes'
        )
        return redirect('/ipam/prefixes/')


class BulkPrefixDiscoverView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Discovers new IPs in selected prefixes (or all if none selected)."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request):
        from .jobs import PrefixDiscoverJob

        pks = request.GET.getlist('pk')
        if pks:
            prefixes = Prefix.objects.filter(pk__in=pks)
        else:
            prefixes = Prefix.objects.all()

        count = 0
        for prefix in prefixes:
            from .jobs import PrefixDiscoverJob, _label_job
            job = PrefixDiscoverJob.enqueue(user=request.user, data={'prefix_id': prefix.pk, 'manual': True}, job_timeout=1800)
            _label_job(job, f'Prefix Discover: {prefix.prefix}')
            count += 1

        messages.info(
            request,
            f'Enqueued discover jobs for {count} prefixes'
        )
        return redirect('/ipam/prefixes/')


class IPPingSingleActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Triggers a ping of a single IP address."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        from django.utils import timezone
        from .utils import ping_host, resolve_dns, _compute_dns_sync

        ip_obj = get_object_or_404(IPAddress, pk=pk)
        ip_str = str(ip_obj.address.ip)
        settings = PluginSettings.load()

        if settings.skip_reserved_ips and ip_obj.status == 'reserved':
            messages.warning(
                request,
                f'{ip_str} has "reserved" status and would be skipped during automatic scans. Pinging anyway since you requested it.',
            )

        ping_data = ping_host(ip_str)
        dns_name = ''
        dns_attempted = False
        if settings.perform_dns_lookup and ping_data['is_reachable']:
            dns_attempted = True
            dns_name = resolve_dns(ip_str, settings.get_dns_servers())

        now = timezone.now()
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

        if ping_data['is_reachable']:
            rtt = ping_data['response_time_ms']
            rtt_str = f' ({rtt:.1f}ms)' if rtt else ''
            messages.success(request, f'{ip_str} is up{rtt_str}')
        else:
            messages.warning(request, f'{ip_str} is down')

        return redirect(ip_obj.get_absolute_url() + 'ping/')


class IPUptimeResetActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Reset uptime statistics for an IP address.

    Creates an UptimeReset audit record (WHO, WHEN, WHY), snapshots the
    current uptime values, and sets PingResult.uptime_reset_at so future
    calculations start fresh. PingHistory records are preserved intact.

    Used when an IP is reassigned to a different device — avoids
    polluting SLA reports with downtime from the previous owner.
    """
    permission_required = 'netbox_ping.change_pingresult'
    http_method_names = ['post']

    def post(self, request, pk):
        from django.utils import timezone

        ip_obj = get_object_or_404(IPAddress, pk=pk)
        reason = (request.POST.get('reason') or '').strip()

        if len(reason) < 5:
            messages.error(
                request,
                'A reason of at least 5 characters is required when resetting '
                'uptime. This is recorded in the audit log.',
            )
            return redirect(ip_obj.get_absolute_url() + 'ping/')

        try:
            ping_result = PingResult.objects.get(ip_address=ip_obj)
        except PingResult.DoesNotExist:
            messages.warning(
                request,
                'No ping data exists for this IP yet — nothing to reset.',
            )
            return redirect(ip_obj.get_absolute_url() + 'ping/')

        # Snapshot current values BEFORE reset (for audit trail)
        previous_reset_at = ping_result.uptime_reset_at
        ping_count = PingHistory.objects.filter(ip_address=ip_obj).count()
        snap_24h = ping_result.uptime_24h
        snap_7d = ping_result.uptime_7d
        snap_30d = ping_result.uptime_30d
        snap_all = ping_result.uptime_all_time

        # Create audit record
        UptimeReset.objects.create(
            ip_address=ip_obj,
            reset_by=request.user if request.user.is_authenticated else None,
            reason=reason,
            previous_reset_at=previous_reset_at,
            ping_count_at_reset=ping_count,
            uptime_24h_at_reset=snap_24h,
            uptime_7d_at_reset=snap_7d,
            uptime_30d_at_reset=snap_30d,
            uptime_all_time_at_reset=snap_all,
        )

        # Apply reset to PingResult — NetBoxModel change log captures this
        ping_result.snapshot()
        ping_result.uptime_reset_at = timezone.now()
        ping_result.consecutive_down_count = 0
        ping_result.save()

        messages.success(
            request,
            f'Uptime statistics reset for {ip_obj}. '
            f'Ping history preserved ({ping_count} records). '
            f'Logged in audit trail as "{reason[:60]}".',
        )
        return redirect(ip_obj.get_absolute_url() + 'ping/')


# ─── Settings View ─────────────────────────────────────────────

class PluginSettingsEditView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Settings edit view with DNS + scheduling config."""
    permission_required = 'netbox_ping.view_pingresult'

    def _get_context(self, form):
        schedules = PrefixSchedule.objects.select_related('prefix').all()
        scan_results = {
            sr.prefix_id: sr
            for sr in SubnetScanResult.objects.all()
        }
        settings = form.instance
        schedule_data = []
        for sched in schedules:
            sr = scan_results.get(sched.prefix_id)
            schedule_data.append({
                'schedule': sched,
                'scan_result': sr,
                'effective_scan': sched.get_effective_scan_interval(settings),
                'effective_discover': sched.get_effective_discover_interval(settings),
            })
        return {
            'form': form,
            'settings': settings,
            'schedule_data': schedule_data,
            'jumphosts': SSHJumpHost.objects.all(),
        }

    def get(self, request):
        settings = PluginSettings.load()
        form = PluginSettingsForm(instance=settings)
        return render(request, 'netbox_ping/settings.html', self._get_context(form))

    def post(self, request):
        settings = PluginSettings.load()
        form = PluginSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved.')
            return redirect('plugins:netbox_ping:settings')
        return render(request, 'netbox_ping/settings.html', self._get_context(form))


class PrefixScheduleEditView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Save per-prefix auto-scan/discover schedule."""
    permission_required = 'netbox_ping.view_pingresult'

    def post(self, request, pk):
        prefix = get_object_or_404(Prefix, pk=pk)
        try:
            schedule = PrefixSchedule.objects.get(prefix=prefix)
        except PrefixSchedule.DoesNotExist:
            schedule = PrefixSchedule(prefix=prefix)

        form = PrefixScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, f'Schedule saved for {prefix.prefix}')
        else:
            messages.error(request, 'Invalid schedule data.')
        return redirect(prefix.get_absolute_url() + 'ping/')


class SendTestEmailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Send a test digest email to verify SMTP configuration."""
    permission_required = 'netbox_ping.view_pingresult'

    def post(self, request):
        from django.conf import settings as django_settings
        from django.core.mail import send_mail
        from .email import build_test_email

        plugin_settings = PluginSettings.load()
        raw = plugin_settings.email_recipients.strip()
        recipients = [r.strip() for r in raw.split(',') if r.strip()] if raw else []

        if not recipients:
            messages.error(request, 'No email recipients configured.')
            return redirect('plugins:netbox_ping:settings')

        subject, html_body, text_body = build_test_email()

        try:
            from_email = getattr(django_settings, 'SERVER_EMAIL', None) or getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'netbox@localhost')
            send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=recipients,
                html_message=html_body,
                fail_silently=False,
            )
            messages.success(request, f'Test email sent to {", ".join(recipients)}.')
        except Exception as e:
            messages.error(request, f'Failed to send test email: {e}')

        return redirect('plugins:netbox_ping:settings')


# ─── SSH Jumphost CRUD Views ────────────────────────────────────

class SSHJumpHostListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """List all SSH jumphosts."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request):
        jumphosts = SSHJumpHost.objects.all()
        return render(request, 'netbox_ping/sshjumphost_list.html', {'jumphosts': jumphosts})


class SSHJumpHostCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Create a new SSH jumphost."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request):
        form = SSHJumpHostForm()
        return render(request, 'netbox_ping/sshjumphost_edit.html', {'form': form})

    def post(self, request):
        form = SSHJumpHostForm(request.POST)
        if form.is_valid():
            jumphost = form.save()
            messages.success(request, f'SSH Jumphost "{jumphost.name}" created.')
            return redirect('plugins:netbox_ping:sshjumphost_list')
        return render(request, 'netbox_ping/sshjumphost_edit.html', {'form': form})


class SSHJumpHostEditView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Edit an existing SSH jumphost."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        jumphost = get_object_or_404(SSHJumpHost, pk=pk)
        form = SSHJumpHostForm(instance=jumphost)
        return render(request, 'netbox_ping/sshjumphost_edit.html', {'form': form, 'object': jumphost})

    def post(self, request, pk):
        jumphost = get_object_or_404(SSHJumpHost, pk=pk)
        form = SSHJumpHostForm(request.POST, instance=jumphost)
        if form.is_valid():
            form.save()
            messages.success(request, f'SSH Jumphost "{jumphost.name}" updated.')
            return redirect('plugins:netbox_ping:sshjumphost_list')
        return render(request, 'netbox_ping/sshjumphost_edit.html', {'form': form, 'object': jumphost})


class SSHJumpHostDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Delete an SSH jumphost."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        jumphost = get_object_or_404(SSHJumpHost, pk=pk)
        used_by_settings = PluginSettings.objects.filter(default_jumphost=jumphost).exists()
        used_by_schedules = PrefixSchedule.objects.filter(custom_jumphost=jumphost).count()
        return render(request, 'netbox_ping/sshjumphost_confirm_delete.html', {
            'object': jumphost,
            'used_by_settings': used_by_settings,
            'used_by_schedules': used_by_schedules,
        })

    def post(self, request, pk):
        jumphost = get_object_or_404(SSHJumpHost, pk=pk)
        name = jumphost.name
        jumphost.delete()
        messages.success(request, f'SSH Jumphost "{name}" deleted.')
        return redirect('plugins:netbox_ping:sshjumphost_list')


class SendDigestNowView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Send a real digest email immediately using current unsent events."""
    permission_required = 'netbox_ping.view_pingresult'

    def post(self, request):
        from datetime import timedelta
        from django.conf import settings as django_settings
        from django.core.mail import send_mail
        from django.utils import timezone
        from .models import ScanEvent, SubnetScanResult
        from .email import build_digest_email

        plugin_settings = PluginSettings.load()
        raw = plugin_settings.email_recipients.strip()
        recipients = [r.strip() for r in raw.split(',') if r.strip()] if raw else []

        if not recipients:
            messages.error(request, 'No email recipients configured.')
            return redirect('plugins:netbox_ping:settings')

        now = timezone.now()
        interval = plugin_settings.email_digest_interval or 1440
        period_start = plugin_settings.email_last_digest_sent or (now - timedelta(minutes=interval))
        period_end = now

        # Collect unsent events
        events = list(
            ScanEvent.objects.filter(digest_sent=False)
            .select_related('ip_address', 'prefix')
            .order_by('created_at')
        )

        # Collect high-utilization prefixes
        high_util = []
        threshold = plugin_settings.email_utilization_threshold
        if threshold > 0:
            for ssr in SubnetScanResult.objects.select_related('prefix').all():
                if ssr.total_hosts > 0 and ssr.utilization >= threshold:
                    high_util.append(ssr)

        if not events and not high_util:
            messages.warning(request, 'No unsent events or high-utilization prefixes to report.')
            return redirect('plugins:netbox_ping:settings')

        subject, html_body, text_body = build_digest_email(
            events, high_util, plugin_settings.email_include_details,
            period_start, period_end, threshold,
        )

        try:
            from_email = getattr(django_settings, 'SERVER_EMAIL', None) or getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'netbox@localhost')
            send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=recipients,
                html_message=html_body,
                fail_silently=False,
            )

            # Mark events as sent and update timestamp
            if events:
                event_ids = [e.pk for e in events]
                ScanEvent.objects.filter(pk__in=event_ids).update(digest_sent=True)
            plugin_settings.email_last_digest_sent = now
            plugin_settings.save(update_fields=['email_last_digest_sent'])

            messages.success(
                request,
                f'Digest sent to {", ".join(recipients)} — {len(events)} event(s), {len(high_util)} high-util prefix(es).'
            )
        except Exception as e:
            messages.error(request, f'Failed to send digest: {e}')

        return redirect('plugins:netbox_ping:settings')


# ─── Audit Reports ──────────────────────────────────────────────

class AuditReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Unified audit report page — date-filtered data with CSV/PDF export.

    Supports 4 report types via ?report= query param:
      - sla          (SLA / Uptime Summary)
      - incidents    (Incident Log)
      - resets       (Uptime Reset Audit)
      - coverage     (DNS Changes + Prefix Coverage)

    Export modes via ?export= query param:
      - csv — download CSV file
      - pdf — render print-friendly template with auto-print JS
    """
    permission_required = 'netbox_ping.view_pinghistory'

    def get(self, request):
        from datetime import date, timedelta
        from django.http import HttpResponse
        import tablib

        from .forms import AuditReportFilterForm
        from .reports import REPORT_REGISTRY

        report_key = request.GET.get('report', 'sla')
        report = REPORT_REGISTRY.get(report_key, REPORT_REGISTRY['sla'])

        # Filter form — prefill from GET, default range = last 30 days
        form_data = request.GET.copy()
        if 'start_date' not in form_data or not form_data.get('start_date'):
            form_data['start_date'] = (date.today() - timedelta(days=30)).isoformat()
        if 'end_date' not in form_data or not form_data.get('end_date'):
            form_data['end_date'] = date.today().isoformat()
        form = AuditReportFilterForm(form_data)

        filters = {}
        if form.is_valid():
            cd = form.cleaned_data
            from django.utils import timezone as tz
            if cd.get('start_date'):
                filters['start'] = tz.make_aware(
                    tz.datetime.combine(cd['start_date'], tz.datetime.min.time()),
                )
            if cd.get('end_date'):
                filters['end'] = tz.make_aware(
                    tz.datetime.combine(cd['end_date'], tz.datetime.max.time()),
                )
            if cd.get('ip_address'):
                filters['ip_address'] = cd['ip_address']
            if cd.get('tenant_id'):
                filters['tenant_id'] = cd['tenant_id'].pk if hasattr(cd['tenant_id'], 'pk') else cd['tenant_id']

        rows = report.get_queryset(filters)
        serialized = [report.row(r) for r in rows]

        export = request.GET.get('export')

        # ─── CSV export ───
        if export == 'csv':
            ds = tablib.Dataset(headers=report.header_labels())
            for r in serialized:
                ds.append([r[k] for k in report.field_keys()])
            response = HttpResponse(ds.csv, content_type='text/csv')
            fname = f'netbox-ping-{report.key}-{filters.get("start", "").__str__()[:10] or "all"}-to-{filters.get("end", "").__str__()[:10] or "now"}.csv'
            fname = fname.replace(' ', '_')
            response['Content-Disposition'] = f'attachment; filename="{fname}"'
            return response

        # ─── PDF export (print-friendly template + auto-print JS) ───
        if export == 'pdf':
            return render(request, 'netbox_ping/audit_report_print.html', {
                'report': report,
                'rows': serialized,
                'filters': filters,
                'form_data': dict(form_data.items()),
                'auto_print': True,
                'row_count': len(serialized),
            })

        # ─── Normal HTML view ───
        return render(request, 'netbox_ping/audit_report.html', {
            'form': form,
            'report': report,
            'report_key': report_key,
            'all_reports': REPORT_REGISTRY,
            'rows': serialized,
            'filters': filters,
            'form_data': dict(form_data.items()),
            'row_count': len(serialized),
        })
