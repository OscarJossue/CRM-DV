from django.urls import path

from .views import AccountSuspendedView, NoPermissionsView, PlatformDashboardView, SmartHomeRedirectView

app_name = "platform_core"

urlpatterns = [
    path("", SmartHomeRedirectView.as_view(), name="smart_home"),
    path("crm/dashboard/", PlatformDashboardView.as_view(), name="dashboard"),
    path("account-suspended/", AccountSuspendedView.as_view(), name="account_suspended"),
    path("no-permissions/", NoPermissionsView.as_view(), name="no_permissions"),
]