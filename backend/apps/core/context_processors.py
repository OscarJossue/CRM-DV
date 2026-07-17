from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _

from apps.core.permissions import user_has_module_permission
from apps.accounts.contractor_access import user_is_contractor_only
from apps.core.tenant import get_user_company, user_is_global_admin


INVALID_NAV_URLS = {"", "#"}


def safe_reverse(route_name):
    """Reverse a named URL without allowing a broken menu link to crash the UI."""
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return "#"


def company_scoped_url(company, route_name=None, raw_url=None):
    """Return a URL inside the active company workspace when applicable."""
    url = raw_url or safe_reverse(route_name)

    if not company or not getattr(company, "slug", None):
        return url

    if not url or url == "#":
        return "#"

    if not url.startswith("/"):
        return url

    if url.startswith(f"/{company.slug}/"):
        return url

    if url.startswith(
        (
            "/crm/",
            "/admin/",
            "/login/",
            "/logout/",
            "/language/",
            "/static/",
            "/media/",
        )
    ):
        return url

    return f"/{company.slug}{url}"


def build_nav_item(
    label,
    url,
    namespace,
    module=None,
    icon_key="default",
    global_only=False,
    staff_only=False,
    owner_only=False,
    active_view_names=None,
    active_view_prefixes=None,
):
    return {
        "label": _(label),
        "url": url,
        "namespace": namespace,
        "module": module,
        "icon_key": icon_key,
        "global_only": global_only,
        "staff_only": staff_only,
        "owner_only": owner_only,
        "active_view_names": tuple(active_view_names or ()),
        "active_view_prefixes": tuple(active_view_prefixes or ()),
    }


def item_is_visible(user, item, is_global_admin):
    # A route that cannot be reversed is never rendered as a dead "#" link.
    if item.get("url") in INVALID_NAV_URLS:
        return False

    if item.get("owner_only"):
        # Owner-only settings are tied to the authoritative account flag, not
        # to a role name that another administrator could create or rename.
        if not getattr(user, "is_company_owner", False):
            return False

    if item.get("staff_only") and not user.is_staff and not user.is_superuser:
        return False

    if item.get("global_only") and not is_global_admin:
        return False

    module_name = item.get("module")

    if module_name and not user_has_module_permission(user, module_name, "can_view"):
        return False

    return True


def mark_item_active(
    item,
    current_namespace,
    current_url_name="",
    request_path="",
):
    namespace = (current_namespace or "").split(":")[-1]
    if namespace.startswith("company_"):
        namespace = namespace[len("company_") :]

    namespace_matches = item.get("namespace") == namespace
    active_view_names = item.get("active_view_names") or ()
    active_view_prefixes = item.get("active_view_prefixes") or ()
    has_view_rules = bool(active_view_names or active_view_prefixes)

    if has_view_rules:
        view_matches = current_url_name in active_view_names or any(
            current_url_name.startswith(prefix)
            for prefix in active_view_prefixes
        )
        item["is_active"] = namespace_matches and view_matches
        return item

    url = item.get("url") or ""
    normalized_url = url.rstrip("/") + "/" if url not in INVALID_NAV_URLS else ""
    normalized_path = request_path.rstrip("/") + "/" if request_path else ""
    path_active = bool(
        normalized_url
        and (
            normalized_path == normalized_url
            or normalized_path.startswith(normalized_url)
        )
    )
    item["is_active"] = namespace_matches or path_active
    return item


def build_group(
    label,
    key,
    icon_key,
    items,
    current_namespace,
    current_url_name="",
    request_path="",
):
    visible_items = []

    for item in items:
        item = mark_item_active(
            item,
            current_namespace,
            current_url_name=current_url_name,
            request_path=request_path,
        )
        visible_items.append(item)

    is_active = any(item.get("is_active") for item in visible_items)

    return {
        "label": _(label),
        "key": key,
        "icon_key": icon_key,
        "items": visible_items,
        "is_active": is_active,
    }


def crm_context(request):
    user = getattr(request, "user", None)

    context = {
        "crm_nav_items": [],
        "crm_nav_groups": [],
        "crm_current_company": None,
        "crm_is_global_admin": False,
        "crm_is_contractor_workspace": False,
        "crm_scope_label": _("Guest"),
    }

    if not user or not user.is_authenticated:
        return context

    company = getattr(request, "current_company", None) or get_user_company(user)
    is_global_admin = user_is_global_admin(user)

    context["crm_current_company"] = company
    context["crm_is_global_admin"] = is_global_admin
    context["crm_is_contractor_workspace"] = user_is_contractor_only(user)

    if is_global_admin:
        context["crm_scope_label"] = _("Global SaaS Admin")
    elif company:
        context["crm_scope_label"] = company.name
    else:
        context["crm_scope_label"] = _("No Company Assigned")

    resolver_match = getattr(request, "resolver_match", None)
    current_namespace = getattr(resolver_match, "namespace", "") if resolver_match else ""
    current_url_name = getattr(resolver_match, "url_name", "") if resolver_match else ""
    request_path = getattr(request, "path", "") or ""

    def nav_url(route_name=None, raw_url=None):
        if is_global_admin:
            return raw_url or safe_reverse(route_name)

        return company_scoped_url(company, route_name=route_name, raw_url=raw_url)

    raw_groups = [
        {
            "label": "Customers & Sales",
            "key": "customers-sales",
            "icon_key": "customers-group",
            "items": [
                build_nav_item("Clients", nav_url("clients:client_list"), "clients", "clients", "clients"),
                build_nav_item(
                    "Opportunities",
                    nav_url("opportunities:opportunity_list"),
                    "opportunities",
                    "opportunities",
                    "opportunities",
                ),
            ],
        },
        {
            "label": "Projects & Field Operations",
            "key": "projects-operations",
            "icon_key": "projects-group",
            "items": [
                build_nav_item("Projects", nav_url("projects:project_list"), "projects", "projects", "projects"),
                build_nav_item(
                    "Inspections",
                    nav_url("inspections:inspection_list"),
                    "inspections",
                    "inspections",
                    "inspections",
                ),
            ],
        },
        {
            "label": "Estimates & Contracts",
            "key": "estimates-contracts",
            "icon_key": "documents-group",
            "items": [
                build_nav_item(
                    "Estimates",
                    nav_url("estimates:estimate_list"),
                    "estimates",
                    "estimates",
                    "estimates",
                ),
                build_nav_item(
                    "Contracts",
                    nav_url("contracts:contract_list"),
                    "contracts",
                    "contracts",
                    "contracts",
                ),
            ],
        },
        {
            "label": "Billing & Finance",
            "key": "billing-finance",
            "icon_key": "finance-group",
            "items": [
                build_nav_item("Invoices", nav_url("invoices:invoice_list"), "invoices", "invoices", "invoices"),
                build_nav_item(
                    "Payments",
                    nav_url("payments:payment_list"),
                    "payments",
                    "payments",
                    "payments",
                    active_view_prefixes=("payment_", "apply_credit_"),
                ),
                build_nav_item(
                    "Client Financial Summary",
                    nav_url("payments:finance_clients"),
                    "payments",
                    "payments",
                    "financial-summary",
                    active_view_prefixes=("finance_",),
                ),
                build_nav_item("Financial Reports", nav_url("reports:reports_home"), "reports", "reports", "reports"),
            ],
        },
        {
            "label": "Purchasing & Suppliers",
            "key": "purchasing-suppliers",
            "icon_key": "suppliers-group",
            "items": [
                build_nav_item(
                    "Suppliers",
                    nav_url("suppliers:supplier_list"),
                    "suppliers",
                    "suppliers",
                    "suppliers",
                    active_view_names=(
                        "dashboard",
                        "document_create_for_supplier",
                        "document_delete",
                    ),
                    active_view_prefixes=("supplier_",),
                ),
                build_nav_item(
                    "Products & Services",
                    nav_url("suppliers:offer_list"),
                    "suppliers",
                    "suppliers",
                    "products",
                    active_view_prefixes=("offer_",),
                ),
                build_nav_item(
                    "Purchases",
                    nav_url("suppliers:purchase_list"),
                    "suppliers",
                    "suppliers",
                    "purchases",
                    active_view_names=("document_create_for_purchase",),
                    active_view_prefixes=("purchase_",),
                ),
                build_nav_item(
                    "Purchasing Reports",
                    nav_url("suppliers:reports"),
                    "suppliers",
                    "suppliers",
                    "supplier-reports",
                    active_view_prefixes=("reports",),
                ),
            ],
        },
        {
            "label": "Team & Settings",
            "key": "team-settings",
            "icon_key": "team-group",
            "items": [
                build_nav_item(
                    "Employees & Users",
                    nav_url("accounts:user_account_list"),
                    "accounts",
                    "users",
                    "users",
                    active_view_prefixes=("user_account_",),
                ),
                build_nav_item(
                    "Roles & Permissions",
                    nav_url("accounts:role_list"),
                    "accounts",
                    "roles",
                    "roles",
                    active_view_prefixes=("role_",),
                ),
                build_nav_item(
                    "Outgoing Email",
                    nav_url("smtp_settings:form"),
                    "smtp_settings",
                    "smtp_settings",
                    "email",
                ),
                build_nav_item(
                    "Language & Region",
                    nav_url("languages:settings"),
                    "languages",
                    None,
                    "languages",
                    owner_only=True,
                ),
                build_nav_item(
                    "Notifications",
                    nav_url("notifications:notification_list"),
                    "notifications",
                    "notifications",
                    "notifications",
                ),
            ],
        },
        {
            "label": "System & Control",
            "key": "system-control",
            "icon_key": "system-group",
            "items": [
                build_nav_item(
                    "Companies",
                    safe_reverse("companies:company_list"),
                    "companies",
                    "companies",
                    "companies",
                    global_only=True,
                ),
                build_nav_item(
                    "Company Modules",
                    safe_reverse("company_modules:company_module_list"),
                    "company_modules",
                    "company_modules",
                    "company-modules",
                    global_only=True,
                    staff_only=True,
                ),
                build_nav_item(
                    "History",
                    nav_url("audit:system_log_list"),
                    "audit",
                    "system_logs",
                    "logs",
                    owner_only=True,
                ),
                build_nav_item(
                    "Technical Administration",
                    "/admin/",
                    "admin",
                    None,
                    "technical-admin",
                    staff_only=True,
                ),
            ],
        },
        {
            "label": "Business Integrations",
            "key": "business-integrations",
            "icon_key": "integrations-group",
            "items": [
                build_nav_item(
                    "Integration Center",
                    nav_url("integrations:dashboard"),
                    "integrations",
                    "integrations",
                    "integrations",
                    active_view_names=(
                        "dashboard",
                        "connection_list",
                        "connection_detail",
                        "connection_settings",
                        "google_credentials_setup",
                        "google_connect",
                        "google_callback",
                        "google_disconnect",
                    ),
                ),
                build_nav_item(
                    "Google Calendar & Meet",
                    nav_url("integrations:calendar_list"),
                    "integrations",
                    "integrations",
                    "google-calendar",
                    active_view_prefixes=("calendar_",),
                ),
                build_nav_item(
                    "Google Drive",
                    nav_url("integrations:drive_list"),
                    "integrations",
                    "integrations",
                    "google-drive",
                    active_view_prefixes=("drive_",),
                ),
                build_nav_item(
                    "Google Analytics",
                    nav_url("integrations:analytics_report"),
                    "integrations",
                    "integrations",
                    "analytics",
                    active_view_prefixes=("analytics_",),
                ),
                build_nav_item(
                    "Sync History",
                    nav_url("integrations:logs"),
                    "integrations",
                    "integrations",
                    "sync-history",
                    active_view_names=("logs",),
                ),
            ],
        },
    ]

    if context["crm_is_contractor_workspace"]:
        raw_groups = [
            {
                "label": "My Field Work",
                "key": "contractor-field-work",
                "icon_key": "projects-group",
                "items": [
                    build_nav_item(
                        "Projects",
                        f"/{company.slug}/field-work/projects/",
                        "contractor_portal",
                        None,
                        "projects",
                    ),
                    build_nav_item(
                        "Inspections",
                        f"/{company.slug}/field-work/inspections/",
                        "contractor_portal",
                        None,
                        "inspections",
                    ),
                ],
            }
        ]

    dashboard_item = build_nav_item(
        "Workspace Dashboard",
        nav_url("dashboard:dashboard_home"),
        "dashboard",
        "dashboard",
        "dashboard",
    )
    dashboard_item = mark_item_active(
        dashboard_item,
        current_namespace,
        current_url_name=current_url_name,
        request_path=request_path,
    )

    calendar_item = build_nav_item(
        "Activity Calendar",
        nav_url("calendar_events:calendar_event_list"),
        "calendar_events",
        "calendar_events",
        "google-calendar",
    )
    calendar_item = mark_item_active(
        calendar_item,
        current_namespace,
        current_url_name=current_url_name,
        request_path=request_path,
    )

    visible_nav_items = []

    if (
        not context["crm_is_contractor_workspace"]
        and item_is_visible(user, dashboard_item, is_global_admin)
    ):
        visible_nav_items.append(dashboard_item)

    if (
        not context["crm_is_contractor_workspace"]
        and item_is_visible(user, calendar_item, is_global_admin)
    ):
        visible_nav_items.append(calendar_item)

    visible_nav_groups = []

    for group in raw_groups:
        visible_items = []

        for item in group.get("items", []):
            if item_is_visible(user, item, is_global_admin):
                visible_items.append(item)

        if not visible_items:
            continue

        visible_nav_groups.append(
            build_group(
                label=group["label"],
                key=group["key"],
                icon_key=group["icon_key"],
                items=visible_items,
                current_namespace=current_namespace,
                current_url_name=current_url_name,
                request_path=request_path,
            )
        )

    context["crm_nav_items"] = visible_nav_items
    context["crm_nav_groups"] = visible_nav_groups

    return context
