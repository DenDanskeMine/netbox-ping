from django import forms
from tenancy.models import Tenant
from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet
from .models import PingResult, PingHistory, SubnetScanResult, PluginSettings, PrefixSchedule, SSHJumpHost


class PingResultFilterForm(NetBoxModelFilterSetForm):
    """Filter form for PingResult list view."""

    model = PingResult
    fieldsets = (
        FieldSet('q', 'filter_id'),
        FieldSet('is_reachable', 'is_stale', 'is_new', name='Status'),
    )
    is_reachable = forms.NullBooleanField(
        required=False,
        label='Reachable',
        widget=forms.Select(choices=[
            ('', '---------'),
            ('true', 'Yes'),
            ('false', 'No'),
        ]),
    )
    is_stale = forms.NullBooleanField(
        required=False,
        label='Stale',
        widget=forms.Select(choices=[
            ('', '---------'),
            ('true', 'Yes'),
            ('false', 'No'),
        ]),
    )
    is_new = forms.NullBooleanField(
        required=False,
        label='New',
        widget=forms.Select(choices=[
            ('', '---------'),
            ('true', 'Yes'),
            ('false', 'No'),
        ]),
    )


class PingHistoryFilterForm(NetBoxModelFilterSetForm):
    """Filter form for PingHistory list view."""

    model = PingHistory
    fieldsets = (
        FieldSet('q', 'filter_id'),
        FieldSet('is_reachable', name='Status'),
    )
    is_reachable = forms.NullBooleanField(
        required=False,
        label='Reachable',
        widget=forms.Select(choices=[
            ('', '---------'),
            ('true', 'Yes'),
            ('false', 'No'),
        ]),
    )


class SubnetScanResultFilterForm(NetBoxModelFilterSetForm):
    """Filter form for SubnetScanResult list view."""

    model = SubnetScanResult
    fieldsets = (
        FieldSet('q', 'filter_id'),
    )


class SSHJumpHostForm(forms.ModelForm):
    """Form for creating/editing an SSH Jumphost."""

    class Meta:
        model = SSHJumpHost
        fields = ('name', 'host', 'port', 'username', 'key_file', 'known_hosts_file', 'description')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class PluginSettingsForm(NetBoxModelForm):
    """Form for editing DNS + scheduling + email settings."""

    class Meta:
        model = PluginSettings
        fields = (
            'dns_server1', 'dns_server2', 'dns_server3', 'perform_dns_lookup',
            'dns_sync_to_netbox', 'dns_clear_on_missing', 'dns_preserve_if_alive',
            'auto_scan_enabled', 'auto_scan_interval',
            'auto_discover_enabled', 'auto_discover_interval',
            'max_prefix_size', 'ping_history_max_records',
            'ping_concurrency', 'ping_timeout', 'ping_count', 'skip_reserved_ips',
            'stale_enabled', 'stale_scans_threshold', 'stale_days_threshold',
            'stale_remove_enabled', 'stale_remove_days',
            'ssh_jumphost_enabled', 'default_jumphost', 'ssh_fallback_to_local',
            'new_ip_days_threshold',
            'email_notifications_enabled', 'email_recipients',
            'email_digest_interval', 'email_include_details',
            'email_utilization_threshold', 'email_on_change_only',
        )
        widgets = {
            'email_recipients': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'admin@example.com, noc@example.com',
            }),
        }


class PrefixScheduleForm(forms.ModelForm):
    """Form for per-prefix schedule overrides."""

    class Meta:
        model = PrefixSchedule
        fields = (
            'scan_mode', 'scan_interval',
            'discover_mode', 'discover_interval',
            'stale_mode',
            'ping_mode', 'custom_jumphost',
        )


class AuditReportFilterForm(forms.Form):
    """Shared filter form for audit reports (all report types)."""

    start_date = forms.DateField(
        required=False,
        label='Start Date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    end_date = forms.DateField(
        required=False,
        label='End Date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    ip_address = forms.CharField(
        required=False,
        label='IP Address / CIDR',
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 10.0.0.5 or 10.0.0.0/24',
            'class': 'form-control',
        }),
        help_text='Single IP matches host; CIDR matches all IPs within the network.',
    )
    tenant_id = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        label='Tenant',
    )
