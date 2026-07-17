from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _

from apps.core.platform_permissions import user_can_platform_action
from apps.platform_users.constants import (
    PLATFORM_MODULE_AUDIT,
    PLATFORM_MODULE_CALENDAR,
    PLATFORM_MODULE_COMPANIES,
    PLATFORM_MODULE_DASHBOARD,
    PLATFORM_MODULE_DOCUMENTS,
    PLATFORM_MODULE_PAYMENTS,
    PLATFORM_MODULE_PLANS,
    PLATFORM_MODULE_RESOURCES,
    PLATFORM_MODULE_SUBSCRIPTIONS,
    PLATFORM_MODULE_SYSTEM_MONITOR,
)


def safe_reverse(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def build_nav_item(
    request,
    *,
    label,
    module,
    url_name,
    active_prefix,
    icon_key="",
):
    url = safe_reverse(url_name)

    if not url:
        return None

    if not user_can_platform_action(request.user, module, "view"):
        return None

    return {
        "label": _(label),
        "url": url,
        "is_active": request.path.startswith(active_prefix),
        "icon_key": icon_key,
    }


def build_group(*, label, icon_key, items, open_by_default=False):
    visible_items = [item for item in items if item]

    if not visible_items:
        return None

    return {
        "label": _(label),
        "icon_key": icon_key,
        "items": visible_items,
        "is_active": any(item["is_active"] for item in visible_items),
        "open_by_default": open_by_default,
    }


def platform_users_context(request):
    user = getattr(request, "user", None)

    is_platform_root = bool(
        user
        and user.is_authenticated
        and user.is_superuser
    )

    is_platform_staff = bool(
        user
        and user.is_authenticated
        and user.is_staff
        and not user.is_superuser
    )

    platform_nav_groups = []
    platform_nav_items = []
    platform_technical_nav_items = []

    if is_platform_root or is_platform_staff:
        overview_items = [
            build_nav_item(
                request,
                label="Control Center",
                module=PLATFORM_MODULE_DASHBOARD,
                url_name="platform_core:dashboard",
                active_prefix="/crm/dashboard/",
                icon_key="control-center",
            ),
            build_nav_item(
                request,
                label="Master Calendar",
                module=PLATFORM_MODULE_CALENDAR,
                url_name="platform_calendar:list",
                active_prefix="/crm/calendar/",
                icon_key="google-calendar",
            ),
        ]

        companies_items = [
            build_nav_item(
                request,
                label="Companies",
                module=PLATFORM_MODULE_COMPANIES,
                url_name="companies:company_list",
                active_prefix="/crm/companies/",
                icon_key="companies",
            ),
            build_nav_item(
                request,
                label="Plans",
                module=PLATFORM_MODULE_PLANS,
                url_name="platform_plans:list",
                active_prefix="/crm/plans/",
                icon_key="plans",
            ),
            build_nav_item(
                request,
                label="Subscriptions",
                module=PLATFORM_MODULE_SUBSCRIPTIONS,
                url_name="platform_subscriptions:list",
                active_prefix="/crm/subscriptions/",
                icon_key="subscriptions",
            ),
        ]

        platform_operations_items = []

        if is_platform_root:
            platform_users_url = safe_reverse("platform_users:user_list")

            if platform_users_url:
                platform_operations_items.append(
                    {
                        "label": _("Platform Users"),
                        "url": platform_users_url,
                        "is_active": request.path.startswith("/crm/platform-users/"),
                        "icon_key": "platform-users",
                    }
                )

        platform_operations_items.extend(
            [
                build_nav_item(
                    request,
                    label="Billing",
                    module=PLATFORM_MODULE_DOCUMENTS,
                    url_name="platform_documents:list",
                    active_prefix="/crm/documents/",
                    icon_key="billing",
                ),
                build_nav_item(
                    request,
                    label="Payments",
                    module=PLATFORM_MODULE_PAYMENTS,
                    url_name="platform_payments:list",
                    active_prefix="/crm/payments/",
                    icon_key="platform-payments",
                ),
                build_nav_item(
                    request,
                    label="Recent Activity",
                    module=PLATFORM_MODULE_AUDIT,
                    url_name="platform_audit:list",
                    active_prefix="/crm/audit/",
                    icon_key="recent-activity",
                ),
            ]
        )

        technical_items = []

        language_url = safe_reverse("platform_languages:settings")
        if language_url:
            technical_items.append(
                {
                    "label": _("Language & Region"),
                    "url": language_url,
                    "is_active": request.path.startswith("/crm/language/"),
                    "icon_key": "languages",
                }
            )

        technical_items.extend(
            [
                build_nav_item(
                    request,
                    label="Resource Usage",
                    module=PLATFORM_MODULE_RESOURCES,
                    url_name="dashboard_metrics:resources_dashboard",
                    active_prefix="/dashboard-metrics/",
                    icon_key="resources",
                ),
                build_nav_item(
                    request,
                    label="System Monitor",
                    module=PLATFORM_MODULE_SYSTEM_MONITOR,
                    url_name="system_monitor:status",
                    active_prefix="/system-monitor/",
                    icon_key="system-monitor",
                ),
            ]
        )

        group_configs = [
            build_group(
                label="Overview",
                icon_key="overview-group",
                items=overview_items,
                open_by_default=True,
            ),
            build_group(
                label="Companies & Subscriptions",
                icon_key="companies-group",
                items=companies_items,
            ),
            build_group(
                label="Platform Operations",
                icon_key="operations-group",
                items=platform_operations_items,
            ),
            build_group(
                label="Technical",
                icon_key="technical-group",
                items=technical_items,
            ),
        ]

        platform_nav_groups = [group for group in group_configs if group]
        has_active_group = any(group["is_active"] for group in platform_nav_groups)
        for index, group in enumerate(platform_nav_groups):
            group["is_open"] = group["is_active"] or (index == 0 and not has_active_group)

        platform_nav_items = [
            item
            for group in platform_nav_groups
            if group["icon_key"] != "technical-group"
            for item in group["items"]
        ]
        platform_technical_nav_items = [
            item
            for group in platform_nav_groups
            if group["icon_key"] == "technical-group"
            for item in group["items"]
        ]

    return {
        "is_platform_root": is_platform_root,
        "is_platform_staff": is_platform_staff,
        "platform_nav_groups": platform_nav_groups,
        # Backward-compatible variables for templates or extensions that still use them.
        "platform_nav_items": platform_nav_items,
        "platform_technical_nav_items": platform_technical_nav_items,
    }
