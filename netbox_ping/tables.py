import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from utilities.tables import register_table_column
from ipam.tables import IPAddressTable, AnnotatedIPAddressTable, PrefixTable
from .models import PingResult, SubnetScanResult


class PingResultTable(NetBoxTable):
    """Table for the PingResult list view."""

    ip_address = tables.Column(
        linkify=True,
        verbose_name='IP Address',
    )
    is_reachable = columns.BooleanColumn(
        verbose_name='Status',
    )
    response_time_ms = tables.Column(
        verbose_name='RTT (ms)',
    )
    dns_name = tables.Column(
        verbose_name='DNS Name',
    )
    last_seen = tables.DateTimeColumn(
        verbose_name='Last Seen',
    )
    last_checked = tables.DateTimeColumn(
        verbose_name='Last Checked',
    )
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    class Meta(NetBoxTable.Meta):
        model = PingResult
        fields = (
            'pk', 'id', 'ip_address', 'is_reachable', 'response_time_ms',
            'dns_name', 'last_seen', 'last_checked', 'actions',
        )
        default_columns = (
            'ip_address', 'is_reachable', 'response_time_ms',
            'dns_name', 'last_seen', 'last_checked',
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
    last_scanned = tables.DateTimeColumn(verbose_name='Last Scanned')
    last_discovered = tables.DateTimeColumn(verbose_name='Last Discovered')
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    class Meta(NetBoxTable.Meta):
        model = SubnetScanResult
        fields = (
            'pk', 'id', 'prefix', 'total_hosts', 'hosts_up',
            'hosts_down', 'last_scanned', 'last_discovered', 'actions',
        )
        default_columns = (
            'prefix', 'total_hosts', 'hosts_up', 'hosts_down', 'last_scanned',
        )


# ─── Register extra columns on core NetBox tables ────────────

PING_STATUS_TEMPLATE = '''
{% if record.ping_result %}
    {% if record.ping_result.is_reachable %}
        <span class="badge text-bg-success">Up</span>
    {% else %}
        <span class="badge text-bg-danger">Down</span>
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
