from django.urls import path

from .views import ResourceDashboardView, ResourceMetricsAPIView

app_name = "dashboard_metrics"

urlpatterns = [
    path("resources/", ResourceDashboardView.as_view(), name="resources_dashboard"),
    path("api/resources/", ResourceMetricsAPIView.as_view(), name="resources_api"),
]