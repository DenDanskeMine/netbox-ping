"""Audit report registry for netbox-ping.

Each report is a class exposing:
  - key: URL slug
  - title: human label
  - description: one-liner
  - columns: list of (field_key, header_label) tuples used for both
    on-screen rendering and CSV export
  - get_queryset(filters): returns the filtered rows for this report
  - row(obj): returns a dict keyed by column field_key with display values
"""

from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    DnsHistory,
    PingHistory,
    PingResult,
    ScanEvent,
    SubnetScanResult,
    UptimeReset,
)


def _clamp_range(start, end):
    """Normalize a date-range filter into aware datetime bounds."""
    if start:
        start = timezone.make_aware(
            timezone.datetime.combine(start, timezone.datetime.min.time()),
        ) if timezone.is_naive(timezone.datetime.combine(start, timezone.datetime.min.time())) else start
    if end:
        end = timezone.make_aware(
            timezone.datetime.combine(end, timezone.datetime.max.time()),
        ) if timezone.is_naive(timezone.datetime.combine(end, timezone.datetime.max.time())) else end
    return start, end


def _apply_ip_filter(queryset, ip_input, relation_prefix='ip_address'):
    """Apply IP address filter to queryset.

    If input is a CIDR (contains '/'), match IPs contained in that network.
    Otherwise, match the specific host IP (ignoring mask).
    """
    if not ip_input:
        return queryset
    ip_input = ip_input.strip()
    if '/' in ip_input:
        # CIDR — match IPs inside this network
        return queryset.filter(**{f'{relation_prefix}__address__net_contained_or_equal': ip_input})
    # Single IP — match by host (ignore mask)
    return queryset.filter(**{f'{relation_prefix}__address__net_host': ip_input})


class BaseReport:
    key = ''
    title = ''
    description = ''
    columns = []  # list of (field_key, header_label)

    def get_queryset(self, filters):
        raise NotImplementedError

    def row(self, obj):
        raise NotImplementedError

    def header_labels(self):
        return [label for _, label in self.columns]

    def field_keys(self):
        return [key for key, _ in self.columns]


class SLAReport(BaseReport):
    """Per-IP uptime summary over the selected date range.

    Calculates uptime percentage directly from PingHistory filtered by
    the date range (not the stored uptime_24h/etc. properties) so it
    exactly reflects the requested window.
    """
    key = 'sla'
    title = 'SLA / Uptime Summary'
    description = 'Per-IP uptime percentage over the date range.'
    columns = [
        ('ip_address', 'IP Address'),
        ('dns_name', 'DNS Name'),
        ('up_pings', 'Up Pings'),
        ('total_pings', 'Total Pings'),
        ('uptime_pct', 'Uptime %'),
        ('last_seen', 'Last Seen'),
        ('resets_in_range', 'Resets in Range'),
    ]

    def get_queryset(self, filters):
        start, end = filters.get('start'), filters.get('end')

        history = PingHistory.objects.all()
        if start:
            history = history.filter(checked_at__gte=start)
        if end:
            history = history.filter(checked_at__lte=end)

        # Group by ip_address, compute up and total
        per_ip = history.values('ip_address').annotate(
            up_pings=Count('id', filter=Q(is_reachable=True)),
            total_pings=Count('id'),
        )
        ip_ids = [row['ip_address'] for row in per_ip]
        stats_by_ip = {row['ip_address']: row for row in per_ip}

        # Get PingResult for dns_name and last_seen + apply scope filters
        qs = PingResult.objects.filter(ip_address_id__in=ip_ids).select_related('ip_address')
        if filters.get('site_id'):
            qs = qs.filter(
                Q(ip_address__assigned_object_id__in=_interface_ids_for_site(filters['site_id']))
                | Q(ip_address__vrf__isnull=False)  # best effort
            )
        if filters.get('tenant_id'):
            qs = qs.filter(ip_address__tenant_id=filters['tenant_id'])
        qs = _apply_ip_filter(qs, filters.get('ip_address'))

        # Attach computed stats
        for row in qs:
            stats = stats_by_ip.get(row.ip_address_id, {'up_pings': 0, 'total_pings': 0})
            row._up_pings = stats['up_pings']
            row._total_pings = stats['total_pings']
            row._uptime_pct = (
                round(stats['up_pings'] / stats['total_pings'] * 100, 2)
                if stats['total_pings'] > 0 else None
            )
            row._resets_in_range = UptimeReset.objects.filter(
                ip_address=row.ip_address,
                reset_at__gte=start if start else timezone.now() - timezone.timedelta(days=36500),
                reset_at__lte=end if end else timezone.now(),
            ).count()

        return sorted(qs, key=lambda r: (r._uptime_pct or 0))

    def row(self, obj):
        return {
            'ip_address': str(obj.ip_address),
            'dns_name': obj.dns_name or '',
            'up_pings': obj._up_pings,
            'total_pings': obj._total_pings,
            'uptime_pct': f'{obj._uptime_pct}%' if obj._uptime_pct is not None else '—',
            'last_seen': obj.last_seen.isoformat() if obj.last_seen else '',
            'resets_in_range': obj._resets_in_range,
        }


class IncidentReport(BaseReport):
    """All ScanEvents in the date range — down/up/stale/discover/DNS events."""
    key = 'incidents'
    title = 'Incident Log'
    description = 'State-change events (up/down/stale/discovered/DNS changed).'
    columns = [
        ('created_at', 'Timestamp'),
        ('event_type', 'Event'),
        ('ip_address', 'IP Address'),
        ('prefix', 'Prefix'),
        ('detail', 'Detail'),
    ]

    def get_queryset(self, filters):
        qs = ScanEvent.objects.select_related('ip_address', 'prefix').order_by('-created_at')
        start, end = filters.get('start'), filters.get('end')
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)
        qs = _apply_ip_filter(qs, filters.get('ip_address'))
        if filters.get('tenant_id'):
            qs = qs.filter(ip_address__tenant_id=filters['tenant_id'])
        return qs

    def row(self, obj):
        detail = ''
        if obj.detail:
            # Flatten JSON detail into a short string
            try:
                detail = ', '.join(f'{k}={v}' for k, v in obj.detail.items())
            except AttributeError:
                detail = str(obj.detail)
        return {
            'created_at': obj.created_at.isoformat(),
            'event_type': obj.get_event_type_display(),
            'ip_address': str(obj.ip_address) if obj.ip_address else '',
            'prefix': str(obj.prefix) if obj.prefix else '',
            'detail': detail,
        }


class UptimeResetReport(BaseReport):
    """Audit log of every uptime reset in the date range."""
    key = 'resets'
    title = 'Uptime Reset Audit'
    description = 'Every uptime reset with user, reason, and before/after snapshot.'
    columns = [
        ('reset_at', 'Reset Timestamp'),
        ('ip_address', 'IP Address'),
        ('reset_by', 'Reset By'),
        ('reason', 'Reason'),
        ('ping_count_at_reset', 'Ping Count'),
        ('uptime_24h_at_reset', '24h % (before)'),
        ('uptime_7d_at_reset', '7d % (before)'),
        ('uptime_30d_at_reset', '30d % (before)'),
        ('uptime_all_time_at_reset', 'All-time % (before)'),
    ]

    def get_queryset(self, filters):
        qs = UptimeReset.objects.select_related('ip_address', 'reset_by').order_by('-reset_at')
        start, end = filters.get('start'), filters.get('end')
        if start:
            qs = qs.filter(reset_at__gte=start)
        if end:
            qs = qs.filter(reset_at__lte=end)
        qs = _apply_ip_filter(qs, filters.get('ip_address'))
        if filters.get('tenant_id'):
            qs = qs.filter(ip_address__tenant_id=filters['tenant_id'])
        return qs

    def row(self, obj):
        def fmt_pct(v):
            return f'{v}%' if v is not None else '—'
        return {
            'reset_at': obj.reset_at.isoformat(),
            'ip_address': str(obj.ip_address),
            'reset_by': obj.reset_by.username if obj.reset_by else '—',
            'reason': obj.reason,
            'ping_count_at_reset': obj.ping_count_at_reset,
            'uptime_24h_at_reset': fmt_pct(obj.uptime_24h_at_reset),
            'uptime_7d_at_reset': fmt_pct(obj.uptime_7d_at_reset),
            'uptime_30d_at_reset': fmt_pct(obj.uptime_30d_at_reset),
            'uptime_all_time_at_reset': fmt_pct(obj.uptime_all_time_at_reset),
        }


class CoverageReport(BaseReport):
    """DNS changes in range + per-prefix scan coverage summary.

    Two-section report combined into a single table via 'section' column.
    """
    key = 'coverage'
    title = 'DNS Changes + Prefix Coverage'
    description = 'DNS change log and per-prefix scan summary.'
    columns = [
        ('section', 'Section'),
        ('timestamp', 'Timestamp'),
        ('target', 'Prefix / IP'),
        ('detail', 'Detail'),
        ('utilization', 'Utilization %'),
    ]

    def get_queryset(self, filters):
        start, end = filters.get('start'), filters.get('end')
        rows = []

        # DNS changes
        dns = DnsHistory.objects.select_related('ip_address').order_by('-changed_at')
        if start:
            dns = dns.filter(changed_at__gte=start)
        if end:
            dns = dns.filter(changed_at__lte=end)
        dns = _apply_ip_filter(dns, filters.get('ip_address'))
        if filters.get('tenant_id'):
            dns = dns.filter(ip_address__tenant_id=filters['tenant_id'])
        for d in dns:
            rows.append({
                'section': 'DNS Change',
                'timestamp': d.changed_at,
                'target': str(d.ip_address),
                'detail': f'"{d.old_dns_name}" → "{d.new_dns_name}"',
                'utilization': None,
            })

        # Prefix coverage — filter by last_scanned inside range
        prefixes = SubnetScanResult.objects.select_related('prefix').order_by('-last_scanned')
        if start:
            prefixes = prefixes.filter(last_scanned__gte=start)
        if end:
            prefixes = prefixes.filter(last_scanned__lte=end)
        if filters.get('site_id'):
            prefixes = prefixes.filter(prefix__site_id=filters['site_id'])
        if filters.get('tenant_id'):
            prefixes = prefixes.filter(prefix__tenant_id=filters['tenant_id'])
        for p in prefixes:
            rows.append({
                'section': 'Prefix Scan',
                'timestamp': p.last_scanned,
                'target': str(p.prefix),
                'detail': (
                    f'up={p.hosts_up} down={p.hosts_down} '
                    f'stale={p.hosts_stale} new={p.hosts_new} '
                    f'total={p.total_hosts}'
                ),
                'utilization': p.utilization,
            })

        # Sort combined by timestamp desc
        rows.sort(key=lambda r: r['timestamp'] or timezone.now(), reverse=True)
        return rows

    def row(self, obj):
        # obj is already a dict for CoverageReport
        return {
            'section': obj['section'],
            'timestamp': obj['timestamp'].isoformat() if obj['timestamp'] else '',
            'target': obj['target'],
            'detail': obj['detail'],
            'utilization': f'{obj["utilization"]}%' if obj['utilization'] is not None else '—',
        }


def _interface_ids_for_site(site_id):
    """Best-effort: return interface ids for a site (for SLA scope filter)."""
    from django.contrib.contenttypes.models import ContentType
    from dcim.models import Interface
    return Interface.objects.filter(device__site_id=site_id).values_list('id', flat=True)


REPORT_REGISTRY = {
    cls.key: cls() for cls in (
        SLAReport,
        IncidentReport,
        UptimeResetReport,
        CoverageReport,
    )
}
