from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SystemLogExportView, SystemLogListView, SystemLogViewSet

app_name = "audit"

router = DefaultRouter()
router.register(r"system-logs", SystemLogViewSet, basename="system_logs_api")

urlpatterns = [
    path("", SystemLogListView.as_view(), name="system_log_list"),
    path("export/", SystemLogExportView.as_view(), name="system_log_export"),
    path("api/", include(router.urls)),
]
