from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("", views.IntegrationDashboardView.as_view(), name="dashboard"),

    # Encrypted company Google connection and OAuth controls.
    path("connections/", views.ConnectionListView.as_view(), name="connection_list"),
    path("connections/google/setup/", views.GoogleCredentialsSetupView.as_view(), name="google_credentials_setup"),
    path("connections/<int:pk>/", views.ConnectionDetailView.as_view(), name="connection_detail"),
    path("connections/<int:pk>/settings/", views.ConnectionSettingsView.as_view(), name="connection_settings"),
    path("google/connect/", views.GoogleConnectStartView.as_view(), name="google_connect"),
    path("google/callback/", views.GoogleCallbackView.as_view(), name="google_callback"),
    path("google/<int:pk>/disconnect/", views.GoogleDisconnectView.as_view(), name="google_disconnect"),

    # Enabled tools for this release.
    path("calendar/", views.CalendarEventListView.as_view(), name="calendar_list"),
    path("calendar/new/", views.CalendarEventCreateView.as_view(), name="calendar_create"),
    path("drive/", views.DriveUploadListView.as_view(), name="drive_list"),
    path("drive/upload/", views.DriveUploadCreateView.as_view(), name="drive_upload"),
    path("analytics/", views.AnalyticsReportView.as_view(), name="analytics_report"),
    path("logs/", views.SyncLogListView.as_view(), name="logs"),

    # Google Sheets, Google Ads and Google Leads remain in the codebase for a
    # later release, but their routes are intentionally disabled for now.
]
