from netbox.api.routers import NetBoxRouter
from . import views

app_name = 'netbox_ping-api'

router = NetBoxRouter()
router.register('ping-results', views.PingResultViewSet)
router.register('ping-history', views.PingHistoryViewSet)
router.register('scan-results', views.SubnetScanResultViewSet)

urlpatterns = router.urls
