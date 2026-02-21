from netbox.search import SearchIndex
from .models import PingResult, SubnetScanResult


class PingResultIndex(SearchIndex):
    model = PingResult
    fields = (
        ('dns_name', 100),
    )


class SubnetScanResultIndex(SearchIndex):
    model = SubnetScanResult
    fields = ()


indexes = (
    PingResultIndex,
    SubnetScanResultIndex,
)
