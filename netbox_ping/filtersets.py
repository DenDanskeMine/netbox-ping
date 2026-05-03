import django_filters
from django.db import models as db_models
from netbox.filtersets import NetBoxModelFilterSet
from .models import PingResult, PingHistory, SubnetScanResult


class PingResultFilterSet(NetBoxModelFilterSet):
    is_reachable = django_filters.BooleanFilter()
    is_skipped = django_filters.BooleanFilter()
    is_stale = django_filters.BooleanFilter()
    is_new = django_filters.BooleanFilter()
    dns_name = django_filters.CharFilter(lookup_expr='icontains')
    last_checked_before = django_filters.DateTimeFilter(
        field_name='last_checked', lookup_expr='lte',
    )
    last_checked_after = django_filters.DateTimeFilter(
        field_name='last_checked', lookup_expr='gte',
    )

    class Meta:
        model = PingResult
        fields = ('id', 'is_reachable', 'is_skipped', 'is_stale', 'is_new', 'dns_name', 'ip_address')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        # Match against DNS name (own and IPAddress.dns_name) and the IP
        # address text. Use net_host_contains so '192.168' matches all IPs
        # within that range (host-based, ignoring mask).
        q = db_models.Q(dns_name__icontains=value)
        q |= db_models.Q(ip_address__dns_name__icontains=value)
        # IP fragment match — '192.168' matches every IP starting with that.
        # Uses django-netfields' host transform, then plain icontains.
        q |= db_models.Q(ip_address__address__host__icontains=value)
        return queryset.filter(q).distinct()


class PingHistoryFilterSet(NetBoxModelFilterSet):
    is_reachable = django_filters.BooleanFilter()
    checked_at_before = django_filters.DateTimeFilter(
        field_name='checked_at', lookup_expr='lte',
    )
    checked_at_after = django_filters.DateTimeFilter(
        field_name='checked_at', lookup_expr='gte',
    )

    class Meta:
        model = PingHistory
        fields = ('id', 'ip_address', 'is_reachable')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        # Match against the cached dns_name on the history row, the linked
        # IPAddress.dns_name, and the IP address text (host fragment).
        q = db_models.Q(dns_name__icontains=value)
        q |= db_models.Q(ip_address__dns_name__icontains=value)
        q |= db_models.Q(ip_address__address__host__icontains=value)
        return queryset.filter(q).distinct()


class SubnetScanResultFilterSet(NetBoxModelFilterSet):
    last_scanned_before = django_filters.DateTimeFilter(
        field_name='last_scanned', lookup_expr='lte',
    )
    last_scanned_after = django_filters.DateTimeFilter(
        field_name='last_scanned', lookup_expr='gte',
    )
    last_discovered_before = django_filters.DateTimeFilter(
        field_name='last_discovered', lookup_expr='lte',
    )
    last_discovered_after = django_filters.DateTimeFilter(
        field_name='last_discovered', lookup_expr='gte',
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
