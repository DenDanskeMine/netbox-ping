from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer
from ..models import PingResult, PingHistory, SubnetScanResult, UptimeReset


class PingResultSerializer(NetBoxModelSerializer):
    uptime_24h = serializers.FloatField(read_only=True, allow_null=True)
    uptime_7d = serializers.FloatField(read_only=True, allow_null=True)
    uptime_30d = serializers.FloatField(read_only=True, allow_null=True)
    uptime_all_time = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = PingResult
        fields = (
            'id', 'url', 'display', 'ip_address', 'is_reachable',
            'is_new', 'discovered_at', 'uptime_reset_at',
            'last_seen', 'response_time_ms', 'dns_name', 'last_checked',
            'uptime_24h', 'uptime_7d', 'uptime_30d', 'uptime_all_time',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'ip_address', 'is_reachable')


class UptimeResetSerializer(serializers.ModelSerializer):
    reset_by_username = serializers.CharField(
        source='reset_by.username', read_only=True, allow_null=True,
    )

    class Meta:
        model = UptimeReset
        fields = (
            'id', 'ip_address', 'reset_by', 'reset_by_username',
            'reset_at', 'reason', 'previous_reset_at',
            'ping_count_at_reset',
            'uptime_24h_at_reset', 'uptime_7d_at_reset',
            'uptime_30d_at_reset', 'uptime_all_time_at_reset',
        )
        read_only_fields = fields


class PingHistorySerializer(NetBoxModelSerializer):
    class Meta:
        model = PingHistory
        fields = (
            'id', 'url', 'display', 'ip_address', 'is_reachable',
            'response_time_ms', 'dns_name', 'checked_at',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'ip_address', 'is_reachable', 'checked_at')


class SubnetScanResultSerializer(NetBoxModelSerializer):
    class Meta:
        model = SubnetScanResult
        fields = (
            'id', 'url', 'display', 'prefix', 'total_hosts', 'hosts_up',
            'hosts_down', 'hosts_new', 'last_scanned', 'last_discovered',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'prefix', 'hosts_up', 'total_hosts')
