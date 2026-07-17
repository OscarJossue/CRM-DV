from django.urls import path

from .views import SystemMonitorAPIView, SystemMonitorView

app_name = "system_monitor"

urlpatterns = [
    path("", SystemMonitorView.as_view(), name="status"),
    path("api/status/", SystemMonitorAPIView.as_view(), name="status_api"),
]