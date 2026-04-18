from django.urls import path
from . import views

app_name = 'netbox_ping'

urlpatterns = [
    # PingResult views
    path('ping-results/', views.PingResultListView.as_view(), name='pingresult_list'),
    path('ping-results/<int:pk>/', views.PingResultView.as_view(), name='pingresult'),
    path('ping-results/<int:pk>/delete/', views.PingResultDeleteView.as_view(), name='pingresult_delete'),
    path('ping-results/delete/', views.PingResultBulkDeleteView.as_view(), name='pingresult_bulk_delete'),

    # PingHistory views
    path('ping-history/', views.PingHistoryListView.as_view(), name='pinghistory_list'),
    path('ping-history/<int:pk>/', views.PingHistoryView.as_view(), name='pinghistory'),
    path('ping-history/<int:pk>/delete/', views.PingHistoryDeleteView.as_view(), name='pinghistory_delete'),
    path('ping-history/delete/', views.PingHistoryBulkDeleteView.as_view(), name='pinghistory_bulk_delete'),

    # SubnetScanResult views
    path('scan-results/', views.SubnetScanResultListView.as_view(), name='subnetscanresult_list'),
    path('scan-results/<int:pk>/', views.SubnetScanResultView.as_view(), name='subnetscanresult'),
    path('scan-results/<int:pk>/delete/', views.SubnetScanResultDeleteView.as_view(), name='subnetscanresult_delete'),

    # Action endpoints
    path('prefix/<int:pk>/scan/', views.PrefixScanActionView.as_view(), name='prefix_scan'),
    path('prefix/<int:pk>/discover/', views.PrefixDiscoverActionView.as_view(), name='prefix_discover'),
    path('ip/<int:pk>/ping/', views.IPPingSingleActionView.as_view(), name='ip_ping'),
    path('ip/<int:pk>/reset-uptime/', views.IPUptimeResetActionView.as_view(), name='ip_reset_uptime'),

    # Bulk action endpoints (from prefix list page)
    path('bulk-scan/', views.BulkPrefixScanView.as_view(), name='bulk_prefix_scan'),
    path('bulk-discover/', views.BulkPrefixDiscoverView.as_view(), name='bulk_prefix_discover'),

    # Per-prefix schedule
    path('prefix/<int:pk>/schedule/', views.PrefixScheduleEditView.as_view(), name='prefix_schedule'),

    # Settings
    path('settings/', views.PluginSettingsEditView.as_view(), name='settings'),
    path('settings/test-email/', views.SendTestEmailView.as_view(), name='test_email'),
    path('settings/send-digest/', views.SendDigestNowView.as_view(), name='send_digest'),

    # SSH Jumphosts
    path('jumphosts/', views.SSHJumpHostListView.as_view(), name='sshjumphost_list'),
    path('jumphosts/add/', views.SSHJumpHostCreateView.as_view(), name='sshjumphost_add'),
    path('jumphosts/<int:pk>/edit/', views.SSHJumpHostEditView.as_view(), name='sshjumphost_edit'),
    path('jumphosts/<int:pk>/delete/', views.SSHJumpHostDeleteView.as_view(), name='sshjumphost_delete'),
]
