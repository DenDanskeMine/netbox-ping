from django.utils import timezone
from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from netbox.api.viewsets import NetBoxModelViewSet
from ..models import PingResult, PingHistory, SubnetScanResult, UptimeReset
from ..filtersets import PingResultFilterSet, PingHistoryFilterSet, SubnetScanResultFilterSet
from .serializers import (
    PingResultSerializer,
    PingHistorySerializer,
    SubnetScanResultSerializer,
    UptimeResetSerializer,
)


class PingResultViewSet(NetBoxModelViewSet):
    queryset = PingResult.objects.select_related('ip_address')
    serializer_class = PingResultSerializer
    filterset_class = PingResultFilterSet

    @action(detail=True, methods=['post'], url_path='reset-uptime')
    def reset_uptime(self, request, pk=None):
        """Reset uptime statistics for this PingResult.

        Requires a non-empty 'reason' in the POST body (min 5 chars).
        Creates an UptimeReset audit record and updates uptime_reset_at.
        Does NOT delete PingHistory — audit trail is preserved.

        Permission: netbox_ping.change_pingresult
        """
        if not request.user.has_perm('netbox_ping.change_pingresult'):
            return Response(
                {'detail': 'You do not have permission to reset uptime.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ping_result = self.get_object()
        reason = (request.data.get('reason') or '').strip()

        if len(reason) < 5:
            return Response(
                {'reason': 'Reason must be at least 5 characters (required for audit).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Snapshot current state
        ping_count = PingHistory.objects.filter(
            ip_address=ping_result.ip_address,
        ).count()

        reset_record = UptimeReset.objects.create(
            ip_address=ping_result.ip_address,
            reset_by=request.user if request.user.is_authenticated else None,
            reason=reason,
            previous_reset_at=ping_result.uptime_reset_at,
            ping_count_at_reset=ping_count,
            uptime_24h_at_reset=ping_result.uptime_24h,
            uptime_7d_at_reset=ping_result.uptime_7d,
            uptime_30d_at_reset=ping_result.uptime_30d,
            uptime_all_time_at_reset=ping_result.uptime_all_time,
        )

        # Apply reset (NetBox change log captures this automatically)
        ping_result.snapshot()
        ping_result.uptime_reset_at = timezone.now()
        ping_result.consecutive_down_count = 0
        ping_result.save()

        return Response(
            {
                'detail': 'Uptime statistics reset.',
                'reset_id': reset_record.pk,
                'reset_at': reset_record.reset_at,
                'ping_count_preserved': ping_count,
                'snapshot': {
                    'uptime_24h_at_reset': reset_record.uptime_24h_at_reset,
                    'uptime_7d_at_reset': reset_record.uptime_7d_at_reset,
                    'uptime_30d_at_reset': reset_record.uptime_30d_at_reset,
                    'uptime_all_time_at_reset': reset_record.uptime_all_time_at_reset,
                },
            },
            status=status.HTTP_200_OK,
        )


class PingHistoryViewSet(NetBoxModelViewSet):
    queryset = PingHistory.objects.select_related('ip_address')
    serializer_class = PingHistorySerializer
    filterset_class = PingHistoryFilterSet


class SubnetScanResultViewSet(NetBoxModelViewSet):
    queryset = SubnetScanResult.objects.select_related('prefix')
    serializer_class = SubnetScanResultSerializer
    filterset_class = SubnetScanResultFilterSet


class UptimeResetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Read-only audit log of uptime resets — for compliance reporting."""
    queryset = UptimeReset.objects.select_related('ip_address', 'reset_by')
    serializer_class = UptimeResetSerializer
    filterset_fields = ['ip_address', 'reset_by']
