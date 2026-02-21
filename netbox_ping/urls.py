from django.urls import path
from . import views

app_name = 'netbox_ping'

urlpatterns = [
    # PingResult views
    path('ping-results/', views.PingResultListView.as_view(), name='pingresult_list'),
    path('ping-results/<int:pk>/', views.PingResultView.as_view(), name='pingresult'),
    path('ping-results/<int:pk>/delete/', views.PingResultDeleteView.as_view(), name='pingresult_delete'),
    path('ping-results/delete/', views.PingResultBulkDeleteView.as_view(), name='pingresult_bulk_delete'),

    # SubnetScanResult views
    path('scan-results/', views.SubnetScanResultListView.as_view(), name='subnetscanresult_list'),
    path('scan-results/<int:pk>/', views.SubnetScanResultView.as_view(), name='subnetscanresult'),
    path('scan-results/<int:pk>/delete/', views.SubnetScanResultDeleteView.as_view(), name='subnetscanresult_delete'),

    # Action endpoints
    path('prefix/<int:pk>/scan/', views.PrefixScanActionView.as_view(), name='prefix_scan'),
    path('prefix/<int:pk>/discover/', views.PrefixDiscoverActionView.as_view(), name='prefix_discover'),
    path('ip/<int:pk>/ping/', views.IPPingSingleActionView.as_view(), name='ip_ping'),

    # Bulk action endpoints (from prefix list page)
    path('bulk-scan/', views.BulkPrefixScanView.as_view(), name='bulk_prefix_scan'),
    path('bulk-discover/', views.BulkPrefixDiscoverView.as_view(), name='bulk_prefix_discover'),

    # Per-prefix schedule
    path('prefix/<int:pk>/schedule/', views.PrefixScheduleEditView.as_view(), name='prefix_schedule'),

    # Settings
    path('settings/', views.PluginSettingsEditView.as_view(), name='settings'),
]
