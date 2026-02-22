from netbox.api.viewsets import NetBoxModelViewSet
from ..models import PingResult, PingHistory, SubnetScanResult
from ..filtersets import PingResultFilterSet, PingHistoryFilterSet, SubnetScanResultFilterSet
from .serializers import PingResultSerializer, PingHistorySerializer, SubnetScanResultSerializer


class PingResultViewSet(NetBoxModelViewSet):
    queryset = PingResult.objects.select_related('ip_address')
    serializer_class = PingResultSerializer
    filterset_class = PingResultFilterSet


class PingHistoryViewSet(NetBoxModelViewSet):
    queryset = PingHistory.objects.select_related('ip_address')
    serializer_class = PingHistorySerializer
    filterset_class = PingHistoryFilterSet


class SubnetScanResultViewSet(NetBoxModelViewSet):
    queryset = SubnetScanResult.objects.select_related('prefix')
    serializer_class = SubnetScanResultSerializer
    filterset_class = SubnetScanResultFilterSet
