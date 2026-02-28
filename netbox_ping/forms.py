from django import forms
from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.rendering import FieldSet
from .models import PingResult, PingHistory, SubnetScanResult, PluginSettings, PrefixSchedule


class PingResultFilterForm(NetBoxModelFilterSetForm):
    """Filter form for PingResult list view."""

    model = PingResult
    fieldsets = (
        FieldSet('q', 'filter_id'),
        FieldSet('is_reachable', 'is_stale', name='Status'),
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
            'ping_concurrency', 'ping_timeout', 'skip_reserved_ips',
            'stale_enabled', 'stale_scans_threshold', 'stale_days_threshold',
            'stale_remove_enabled', 'stale_remove_days',
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
        )
