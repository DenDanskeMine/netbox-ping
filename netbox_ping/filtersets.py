import django_filters
from django.db import models as db_models
from netbox.filtersets import NetBoxModelFilterSet
from .models import PingResult, SubnetScanResult


class PingResultFilterSet(NetBoxModelFilterSet):
    is_reachable = django_filters.BooleanFilter()
    dns_name = django_filters.CharFilter(lookup_expr='icontains')
    last_checked_before = django_filters.DateTimeFilter(
        field_name='last_checked', lookup_expr='lte',
    )
    last_checked_after = django_filters.DateTimeFilter(
        field_name='last_checked', lookup_expr='gte',
    )

    class Meta:
        model = PingResult
        fields = ('id', 'is_reachable', 'dns_name', 'ip_address')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            db_models.Q(dns_name__icontains=value)
        )


class SubnetScanResultFilterSet(NetBoxModelFilterSet):
    last_scanned_before = django_filters.DateTimeFilter(
        field_name='last_scanned', lookup_expr='lte',
    )
    last_scanned_after = django_filters.DateTimeFilter(
        field_name='last_scanned', lookup_expr='gte',
    )

    class Meta:
        model = SubnetScanResult
        fields = ('id', 'prefix')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            db_models.Q(prefix__prefix__net_contains_or_equals=value)
        )
