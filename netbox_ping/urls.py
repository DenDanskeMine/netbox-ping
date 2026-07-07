from django.urls import path
from netbox.views.generic import ObjectChangeLogView, ObjectJournalView
from . import views
from .models import VrfPolicy, PrefixSchedule

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

    # Per-prefix policy save from the Prefix detail tab
    path('prefix/<int:pk>/schedule/', views.PrefixScheduleSaveView.as_view(), name='prefix_schedule'),

    # Prefix Policy management (standard NetBox object views)
    path('prefix-policies/', views.PrefixScheduleListView.as_view(), name='prefixschedule_list'),
    path('prefix-policies/add/', views.PrefixScheduleEditView.as_view(), name='prefixschedule_add'),
    path('prefix-policies/delete/', views.PrefixScheduleBulkDeleteView.as_view(), name='prefixschedule_bulk_delete'),
    path('prefix-policies/<int:pk>/', views.PrefixScheduleView.as_view(), name='prefixschedule'),
    path('prefix-policies/<int:pk>/edit/', views.PrefixScheduleEditView.as_view(), name='prefixschedule_edit'),
    path('prefix-policies/<int:pk>/delete/', views.PrefixScheduleDeleteView.as_view(), name='prefixschedule_delete'),
    path('prefix-policies/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='prefixschedule_changelog', kwargs={'model': PrefixSchedule}),
    path('prefix-policies/<int:pk>/journal/', ObjectJournalView.as_view(), name='prefixschedule_journal', kwargs={'model': PrefixSchedule}),

    # Per-VRF policy (save from VRF detail tab)
    path('vrf/<int:pk>/policy/', views.VrfPolicySaveView.as_view(), name='vrf_policy'),

    # VRF Ping Policy central management (standard NetBox object views)
    path('vrf-policies/', views.VrfPolicyListView.as_view(), name='vrfpolicy_list'),
    path('vrf-policies/add/', views.VrfPolicyEditView.as_view(), name='vrfpolicy_add'),
    path('vrf-policies/delete/', views.VrfPolicyBulkDeleteView.as_view(), name='vrfpolicy_bulk_delete'),
    path('vrf-policies/<int:pk>/', views.VrfPolicyView.as_view(), name='vrfpolicy'),
    path('vrf-policies/<int:pk>/edit/', views.VrfPolicyEditView.as_view(), name='vrfpolicy_edit'),
    path('vrf-policies/<int:pk>/delete/', views.VrfPolicyDeleteView.as_view(), name='vrfpolicy_delete'),
    path('vrf-policies/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='vrfpolicy_changelog', kwargs={'model': VrfPolicy}),
    path('vrf-policies/<int:pk>/journal/', ObjectJournalView.as_view(), name='vrfpolicy_journal', kwargs={'model': VrfPolicy}),

    # Audit Reports
    path('reports/', views.AuditReportView.as_view(), name='audit_report'),

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
