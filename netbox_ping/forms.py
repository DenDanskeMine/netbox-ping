from django import forms
from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.rendering import FieldSet
from .models import PingResult, SubnetScanResult, PluginSettings, PrefixSchedule


class PingResultFilterForm(NetBoxModelFilterSetForm):
    """Filter form for PingResult list view."""

    model = PingResult
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
    """Form for editing DNS + scheduling settings."""

    class Meta:
        model = PluginSettings
        fields = (
            'dns_server1', 'dns_server2', 'dns_server3', 'perform_dns_lookup',
            'auto_scan_enabled', 'auto_scan_interval',
            'auto_discover_enabled', 'auto_discover_interval',
            'max_prefix_size', 'ping_history_max_records',
        )


class PrefixScheduleForm(forms.ModelForm):
    """Form for per-prefix schedule overrides."""

    class Meta:
        model = PrefixSchedule
        fields = (
            'scan_mode', 'scan_interval',
            'discover_mode', 'discover_interval',
        )
