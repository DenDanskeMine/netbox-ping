import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from ipam.models import Prefix, IPAddress

from .models import PingResult, PingHistory, SubnetScanResult, PluginSettings, PrefixSchedule
from .tables import PingResultTable, PingHistoryTable, SubnetScanResultTable
from .filtersets import PingResultFilterSet, PingHistoryFilterSet, SubnetScanResultFilterSet
from .forms import PingResultFilterForm, SubnetScanResultFilterForm, PluginSettingsForm, PrefixScheduleForm

logger = logging.getLogger('netbox.netbox_ping')


# ─── PingResult CRUD Views ─────────────────────────────────────

class PingResultListView(generic.ObjectListView):
    queryset = PingResult.objects.select_related('ip_address')
    table = PingResultTable
    filterset = PingResultFilterSet
    filterset_form = PingResultFilterForm


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
        return {
            'ping_result': ping_result,
            'history_table': history_table,
        }


# ─── Action Views (trigger scans) ──────────────────────────────

class PrefixScanActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Triggers a scan of all existing IPs in a prefix."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        from .jobs import PrefixScanJob

        prefix = get_object_or_404(Prefix, pk=pk)
        PrefixScanJob.enqueue(user=request.user, data={'prefix_id': prefix.pk})
        messages.info(request, f'Scan job enqueued for {prefix.prefix}')
        return redirect(prefix.get_absolute_url() + 'ping/')


class PrefixDiscoverActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Triggers discovery of new IPs in a prefix."""
    permission_required = 'netbox_ping.view_pingresult'

    def get(self, request, pk):
        from .jobs import PrefixDiscoverJob

        prefix = get_object_or_404(Prefix, pk=pk)
        PrefixDiscoverJob.enqueue(user=request.user, data={'prefix_id': prefix.pk})
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
            PrefixScanJob.enqueue(user=request.user, data={'prefix_id': prefix.pk})
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
            PrefixDiscoverJob.enqueue(user=request.user, data={'prefix_id': prefix.pk})
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
        from .utils import ping_host, resolve_dns

        ip_obj = get_object_or_404(IPAddress, pk=pk)
        ip_str = str(ip_obj.address.ip)
        settings = PluginSettings.load()

        ping_data = ping_host(ip_str)
        dns_name = ''
        if settings.perform_dns_lookup and ping_data['is_reachable']:
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

        if ping_data['is_reachable']:
            rtt = ping_data['response_time_ms']
            rtt_str = f' ({rtt:.1f}ms)' if rtt else ''
            messages.success(request, f'{ip_str} is up{rtt_str}')
        else:
            messages.warning(request, f'{ip_str} is down')

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
