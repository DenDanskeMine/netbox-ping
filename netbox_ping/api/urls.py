from netbox.api.routers import NetBoxRouter
from . import views

app_name = 'netbox_ping-api'

router = NetBoxRouter()
router.register('ping-results', views.PingResultViewSet)
router.register('ping-history', views.PingHistoryViewSet)
router.register('scan-results', views.SubnetScanResultViewSet)
router.register('uptime-resets', views.UptimeResetViewSet, basename='uptimereset')

urlpatterns = router.urls
