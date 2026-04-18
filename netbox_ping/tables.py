import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from utilities.tables import register_table_column
from ipam.tables import IPAddressTable, AnnotatedIPAddressTable, PrefixTable
from .models import PingResult, PingHistory, SubnetScanResult, DnsHistory


PINGRESULT_STATUS_TEMPLATE = '''
{% if record.is_skipped %}
    <span class="badge text-bg-warning">Skipped</span>
{% elif record.is_stale %}
    <span class="badge" style="background-color:#e67e22;color:#fff;">Stale</span>
{% elif record.is_reachable %}
    <span class="badge text-bg-success">Up</span>
{% else %}
    <span class="badge text-bg-danger">Down</span>
{% endif %}
{% if record.is_new %}
    <span class="badge text-bg-info">New</span>
{% endif %}
'''

PINGRESULT_HISTORY_TEMPLATE = '''
<a href="{% url 'plugins:netbox_ping:pinghistory_list' %}?ip_address={{ record.ip_address_id }}"
   class="btn btn-sm btn-outline-secondary" title="View history">
    <span class="mdi mdi-history"></span>
</a>
'''


def _uptime_cell(value, record):
    """Render uptime % as a colored badge."""
    from django.utils.safestring import mark_safe
    if value is None:
        return mark_safe('<span class="text-muted">—</span>')
    color = record.uptime_color(value)
    return mark_safe(f'<span class="badge text-bg-{color}">{value}%</span>')


class PingResultTable(NetBoxTable):
    """Table for the PingResult list view."""

    ip_address = tables.Column(
        linkify=True,
        verbose_name='IP Address',
    )
    status = columns.TemplateColumn(
        template_code=PINGRESULT_STATUS_TEMPLATE,
        verbose_name='Status',
        order_by='is_reachable',
    )
    response_time_ms = tables.Column(
        verbose_name='RTT (ms)',
    )
    dns_name = tables.Column(
        verbose_name='DNS Name',
    )
    consecutive_down_count = tables.Column(
        verbose_name='Down Count',
    )
    last_seen = tables.DateTimeColumn(
        verbose_name='Last Seen',
    )
    last_checked = tables.DateTimeColumn(
        verbose_name='Last Checked',
    )
    uptime_24h = tables.Column(
        accessor='uptime_24h',
        verbose_name='Uptime 24h',
        orderable=False,
    )
    uptime_7d = tables.Column(
        accessor='uptime_7d',
        verbose_name='Uptime 7d',
        orderable=False,
    )
    uptime_30d = tables.Column(
        accessor='uptime_30d',
        verbose_name='Uptime 30d',
        orderable=False,
    )
    history = columns.TemplateColumn(
        template_code=PINGRESULT_HISTORY_TEMPLATE,
        verbose_name='History',
        orderable=False,
    )
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    def render_uptime_24h(self, value, record):
        return _uptime_cell(value, record)

    def render_uptime_7d(self, value, record):
        return _uptime_cell(value, record)

    def render_uptime_30d(self, value, record):
        return _uptime_cell(value, record)

    class Meta(NetBoxTable.Meta):
        model = PingResult
        fields = (
            'pk', 'id', 'ip_address', 'status', 'response_time_ms',
            'dns_name', 'consecutive_down_count',
            'uptime_24h', 'uptime_7d', 'uptime_30d',
            'last_seen', 'last_checked', 'history', 'actions',
        )
        default_columns = (
            'ip_address', 'status', 'response_time_ms',
            'dns_name', 'uptime_24h', 'uptime_7d',
            'consecutive_down_count', 'last_seen', 'last_checked',
            'history',
        )


PINGHISTORY_STATUS_TEMPLATE = '''
{% if record.is_reachable %}
    <span class="badge text-bg-success">Up</span>
{% else %}
    <span class="badge text-bg-danger">Down</span>
{% endif %}
'''


class PingHistoryTable(NetBoxTable):
    """Table for the PingHistory list view."""

    ip_address = tables.Column(
        linkify=True,
        verbose_name='IP Address',
    )
    checked_at = tables.DateTimeColumn(
        verbose_name='Checked At',
    )
    status = columns.TemplateColumn(
        template_code=PINGHISTORY_STATUS_TEMPLATE,
        verbose_name='Status',
        order_by='is_reachable',
    )
    response_time_ms = tables.Column(
        verbose_name='RTT (ms)',
    )
    dns_name = tables.Column(
        verbose_name='DNS Name',
    )
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    class Meta(NetBoxTable.Meta):
        model = PingHistory
        fields = (
            'pk', 'id', 'ip_address', 'checked_at', 'status',
            'response_time_ms', 'dns_name', 'actions',
        )
        default_columns = (
            'ip_address', 'checked_at', 'status',
            'response_time_ms', 'dns_name',
        )


class SubnetScanResultTable(NetBoxTable):
    """Table for the SubnetScanResult list view."""

    prefix = tables.Column(
        linkify=True,
        verbose_name='Prefix',
    )
    total_hosts = tables.Column(verbose_name='Total Hosts')
    hosts_up = tables.Column(verbose_name='Hosts Up')
    hosts_down = tables.Column(verbose_name='Hosts Down')
    hosts_skipped = tables.Column(verbose_name='Hosts Skipped')
    hosts_stale = tables.Column(verbose_name='Hosts Stale')
    hosts_new = tables.Column(verbose_name='Hosts New')
    last_scanned = tables.DateTimeColumn(verbose_name='Last Scanned')
    last_discovered = tables.DateTimeColumn(verbose_name='Last Discovered')
    next_scan_at = tables.DateTimeColumn(verbose_name='Next Scan')
    next_discover_at = tables.DateTimeColumn(verbose_name='Next Discover')
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    class Meta(NetBoxTable.Meta):
        model = SubnetScanResult
        fields = (
            'pk', 'id', 'prefix', 'total_hosts', 'hosts_up',
            'hosts_down', 'hosts_skipped', 'hosts_stale', 'hosts_new',
            'last_scanned', 'next_scan_at', 'last_discovered', 'next_discover_at', 'actions',
        )
        default_columns = (
            'prefix', 'total_hosts', 'hosts_up', 'hosts_down',
            'hosts_stale', 'hosts_new', 'last_scanned', 'next_scan_at',
        )


class DnsHistoryTable(tables.Table):
    """Table for DNS change history on the IP address ping tab."""

    changed_at = tables.DateTimeColumn(verbose_name='Changed At')
    old_dns_name = tables.Column(verbose_name='Old DNS Name')
    new_dns_name = tables.Column(verbose_name='New DNS Name')

    class Meta:
        model = DnsHistory
        fields = ('changed_at', 'old_dns_name', 'new_dns_name')
        attrs = {'class': 'table table-hover'}


# ─── Register extra columns on core NetBox tables ────────────

PING_STATUS_TEMPLATE = '''
{% if record.ping_result %}
    {% if record.ping_result.is_skipped %}
        <span class="badge text-bg-warning">Skipped</span>
    {% elif record.ping_result.is_stale %}
        <span class="badge" style="background-color:#e67e22;color:#fff;">Stale</span>
    {% elif record.ping_result.is_reachable %}
        <span class="badge text-bg-success">Up</span>
    {% else %}
        <span class="badge text-bg-danger">Down</span>
    {% endif %}
    {% if record.ping_result.is_new %}
        <span class="badge text-bg-info">New</span>
    {% endif %}
{% else %}
    <span class="text-muted">&mdash;</span>
{% endif %}
'''

SCAN_STATUS_TEMPLATE = '''
{% if record.scan_result %}
    <span class="badge text-bg-info">
        {{ record.scan_result.hosts_up }}/{{ record.scan_result.total_hosts }} up
    </span>
    {% if record.scan_result.hosts_new %}
        <span class="badge text-bg-info">{{ record.scan_result.hosts_new }} new</span>
    {% endif %}
    {% if record.scan_result.hosts_stale %}
        <span class="badge" style="background-color:#e67e22;color:#fff;">{{ record.scan_result.hosts_stale }} stale</span>
    {% endif %}
    {% if record.scan_result.hosts_skipped %}
        <span class="badge text-bg-warning">{{ record.scan_result.hosts_skipped }} skipped</span>
    {% endif %}
{% else %}
    <span class="text-muted">&mdash;</span>
{% endif %}
'''

# Ping status on IPAddress tables (both base and annotated variants)
for ip_table in (IPAddressTable, AnnotatedIPAddressTable):
    register_table_column(
        columns.TemplateColumn(
            template_code=PING_STATUS_TEMPLATE,
            verbose_name='Ping Status',
            order_by='ping_result__is_reachable',
        ),
        'ping_status',
        ip_table,
    )

# Scan status on Prefix table
register_table_column(
    columns.TemplateColumn(
        template_code=SCAN_STATUS_TEMPLATE,
        verbose_name='Ping Status',
        order_by='scan_result__hosts_up',
    ),
    'ping_status',
    PrefixTable,
)
