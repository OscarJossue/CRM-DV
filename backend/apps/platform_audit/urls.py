from django.urls import path

from .views import PlatformAuditDetailView, PlatformAuditListView

app_name = "platform_audit"

urlpatterns = [
    path("", PlatformAuditListView.as_view(), name="list"),
    path("<int:id_audit>/", PlatformAuditDetailView.as_view(), name="detail"),
]