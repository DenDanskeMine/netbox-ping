from netbox.api.viewsets import NetBoxModelViewSet
from ..models import PingResult, SubnetScanResult
from ..filtersets import PingResultFilterSet, SubnetScanResultFilterSet
from .serializers import PingResultSerializer, SubnetScanResultSerializer


class PingResultViewSet(NetBoxModelViewSet):
    queryset = PingResult.objects.select_related('ip_address')
    serializer_class = PingResultSerializer
    filterset_class = PingResultFilterSet


class SubnetScanResultViewSet(NetBoxModelViewSet):
    queryset = SubnetScanResult.objects.select_related('prefix')
    serializer_class = SubnetScanResultSerializer
    filterset_class = SubnetScanResultFilterSet
