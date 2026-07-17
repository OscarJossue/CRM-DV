from django.urls import reverse

from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code
from apps.core.permissions import user_has_module_permission
from apps.accounts.contractor_access import user_is_contractor_only

from apps.core.platform_permissions import (
    user_is_platform_root,
    user_is_platform_staff,
    user_can_platform_action,
)
from apps.platform_users.constants import (
    PLATFORM_MODULE_AUDIT,
    PLATFORM_MODULE_CALENDAR,
    PLATFORM_MODULE_COMPANIES,
    PLATFORM_MODULE_DASHBOARD,
    PLATFORM_MODULE_DOCUMENTS,
    PLATFORM_MODULE_EMAIL,
    PLATFORM_MODULE_NOTIFICATIONS,
    PLATFORM_MODULE_PAYMENTS,
    PLATFORM_MODULE_PLANS,
    PLATFORM_MODULE_RESOURCES,
    PLATFORM_MODULE_SUBSCRIPTIONS,
    PLATFORM_MODULE_SYSTEM_MONITOR,
)


PLATFORM_ROUTE_MAP = [
    (PLATFORM_MODULE_DASHBOARD, "platform_core:dashboard"),
    (PLATFORM_MODULE_COMPANIES, "companies:company_list"),
    (PLATFORM_MODULE_PLANS, "platform_plans:list"),
    (PLATFORM_MODULE_SUBSCRIPTIONS, "platform_subscriptions:list"),
    (PLATFORM_MODULE_DOCUMENTS, "platform_documents:list"),
    (PLATFORM_MODULE_PAYMENTS, "platform_payments:list"),
    (PLATFORM_MODULE_CALENDAR, "platform_calendar:list"),
    (PLATFORM_MODULE_EMAIL, "platform_email:list"),
    (PLATFORM_MODULE_NOTIFICATIONS, "platform_notifications:list"),
    (PLATFORM_MODULE_AUDIT, "platform_audit:list"),
    (PLATFORM_MODULE_RESOURCES, "dashboard_metrics:resources_dashboard"),
    (PLATFORM_MODULE_SYSTEM_MONITOR, "system_monitor:status"),
]


def get_first_allowed_platform_url(user):
    if user_is_platform_root(user):
        return reverse("platform_core:dashboard")

    if not user_is_platform_staff(user):
        return None

    for module_name, route_name in PLATFORM_ROUTE_MAP:
        if user_can_platform_action(user, module_name, "view"):
            return reverse(route_name)

    return reverse("platform_core:no_permissions")


CRM_ROUTE_MAP = [
    ("dashboard", "dashboard/"),
    ("clients", "clients/"),
    ("leads", "leads/"),
    ("opportunities", "opportunities/"),
    ("calendar_events", "calendar-events/"),
    ("projects", "projects/"),
    ("inspections", "inspections/"),
    ("supervision", "audit/"),
    ("estimates", "estimates/"),
    ("contracts", "contracts/"),
    ("invoices", "invoices/"),
    ("payments", "payments/"),
    ("reports", "reports/"),
    ("users", "users/"),
    ("roles", "roles/"),
    ("system_logs", "system-logs/"),
    ("smtp_settings", "smtp-settings/"),
    ("notifications", "notifications/"),
]


def get_first_allowed_company_url(user):
    company = getattr(user, "id_company", None)

    if not company or not getattr(company, "slug", None):
        return None

    if user_is_contractor_only(user):
        return f"/{company.slug}/field-work/inspections/"

    for module_name, path in CRM_ROUTE_MAP:
        if user_has_module_permission(user, module_name, "can_view"):
            return f"/{company.slug}/{path}"

    return None


def get_user_dashboard_url(user):
    if not user or not user.is_authenticated:
        return "/login/"

    if user_is_platform_root(user) or user_is_platform_staff(user):
        return get_first_allowed_platform_url(user)

    if get_user_runtime_access_code(user) != ACCESS_ALLOWED:
        return reverse("platform_core:account_suspended")

    company = getattr(user, "id_company", None)

    if company and getattr(company, "slug", None):
        return get_first_allowed_company_url(user) or reverse("platform_core:no_permissions")

    return reverse("platform_core:account_suspended")
