from netbox.api.serializers import NetBoxModelSerializer
from ..models import PingResult, PingHistory, SubnetScanResult


class PingResultSerializer(NetBoxModelSerializer):
    class Meta:
        model = PingResult
        fields = (
            'id', 'url', 'display', 'ip_address', 'is_reachable',
            'last_seen', 'response_time_ms', 'dns_name', 'last_checked',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'ip_address', 'is_reachable')


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
            'hosts_down', 'last_scanned', 'last_discovered',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'prefix', 'hosts_up', 'total_hosts')
