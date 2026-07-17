from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import translation

from apps.core.permissions import user_has_module_permission
from apps.accounts.contractor_access import user_is_contractor_only


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# URL namespaces used by the company CRM and their role-permission module key.
CRM_NAMESPACE_MODULE_MAP = {
    "dashboard": "dashboard",
    "clients": "clients",
    "leads": "leads",
    "opportunities": "opportunities",
    "projects": "projects",
    "inspections": "inspections",
    "evidence": "evidence",
    "supervision": "supervision",
    "calendar": "calendar_events",
    "calendar_alt": "calendar_events",
    "calendar_events": "calendar_events",
    "estimates": "estimates",
    "invoices": "invoices",
    "payments": "payments",
    "suppliers": "suppliers",
    "integrations": "integrations",
    "contracts": "contracts",
    "reports": "reports",
    "smtp_settings": "smtp_settings",
    "notifications": "notifications",
    "employees": "users",
    "audit": "system_logs",
    "system_logs": "system_logs",
    "user_activities": "system_logs",
    "company_modules": "company_modules",
}

# Account URLs are shared by users and roles, so they are resolved by url_name.
ACCOUNT_ROUTE_PREFIX_MODULE_MAP = {
    "role": "roles",
    "role_permission": "roles",
    "user_account": "users",
}

SENSITIVE_APPROVE_KEYWORDS = (
    "approve",
    "reject",
    "void",
    "cancel",
    "confirm",
    "verify",
    "complete",
    "final_audit",
    "mark_signed",
    "suspend",
)

CREATE_KEYWORDS = ("create", "onboarding", "upload", "export")
EDIT_KEYWORDS = (
    "edit",
    "update",
    "send",
    "generate",
    "mark_sent",
    "mark_paid",
    "mark_pending",
    "activate",
    "deactivate",
    "status",
    "note",
    "gallery_upload",
    "gallery_delete",
    "mark_read",
    "mark_unread",
    "mark_all_read",
    "archive",
    "apply_credit",
    "sync",
    "manage",
    "test",
    "connect",
    "disconnect",
    "settings",
)
DELETE_KEYWORDS = ("delete", "destroy")

PUBLIC_ROUTE_PREFIXES = (
    "public_",
    "password_reset",
)

# These POST routes are not general create/edit permissions. They are a narrow
# self-service surface for contractor-only accounts, and every target view still
# verifies that the work is assigned to the current user and is not locked.
CONTRACTOR_SELF_SERVICE_ROUTE_NAMES = {
    "project_contractor_update",
    "project_evidence_create",
    "project_evidence_delete",
    "project_gallery_delete",
    "project_submit_audit",
    "project_submit_review",
    "inspection_contractor_update",
    "inspection_gallery_upload",
    "inspection_gallery_delete",
    "inspection_submit_audit",
    "inspection_submit_review",
    "assignment_contractor_update",
    "assignment_gallery_upload",
    "assignment_gallery_delete",
    "assignment_submit_audit",
    "assignment_submit_review",
}

SKIPPED_PATH_PREFIXES = (
    "/admin/",
    "/health/",
    "/login/",
    "/logout/",
    "/crm/",  # Platform SaaS admin has its own platform permission system.
    "/api/companies/",
    "/metrics",
    "/static/",
    "/media/",
    "/dashboard-metrics/",  # Platform technical dashboard.
    "/system-monitor/",     # Platform technical dashboard.
)


def _normalize_namespace(namespace):
    namespace = (namespace or "").split(":")[-1]

    if namespace.startswith("company_"):
        namespace = namespace[len("company_"):]

    return namespace


def _module_from_route(namespace, url_name, view_func):
    view_class = getattr(view_func, "view_class", None)
    module_name = getattr(view_class, "module_name", None)

    if module_name:
        return module_name

    namespace = _normalize_namespace(namespace)
    url_name = url_name or ""

    if namespace in {"accounts", "company_accounts"}:
        for prefix, module_name in ACCOUNT_ROUTE_PREFIX_MODULE_MAP.items():
            if url_name.startswith(prefix):
                return module_name
        return None

    return CRM_NAMESPACE_MODULE_MAP.get(namespace)


def _permission_from_route(url_name, request_method, view_func):
    url_name = url_name or ""

    for prefix in PUBLIC_ROUTE_PREFIXES:
        if url_name.startswith(prefix):
            return None

    for keyword in SENSITIVE_APPROVE_KEYWORDS:
        if keyword in url_name:
            return "can_approve"

    for keyword in CREATE_KEYWORDS:
        if keyword in url_name:
            return "can_create"

    for keyword in EDIT_KEYWORDS:
        if keyword in url_name:
            return "can_edit"

    for keyword in DELETE_KEYWORDS:
        if keyword in url_name:
            return "can_delete"

    if request_method not in SAFE_METHODS:
        return "can_edit"

    view_class = getattr(view_func, "view_class", None)
    permission_required = getattr(view_class, "permission_required", None)

    if permission_required:
        return permission_required

    return "can_view"


class CompanyLanguageMiddleware:
    """Activate the correct interface language for every request.

    Company users inherit the language configured for their company workspace.
    Platform administrators use their personal ``preferred_language`` value.
    Anonymous login pages use Django's language cookie selected by the visitor.
    Technical/API endpoints remain in English and public customer documents keep
    using the language configured for the document company.
    """

    TECHNICAL_ENGLISH_PREFIXES = (
        "/admin/",
        "/api/",
        "/metrics",
        "/health/",
        "/static/",
        "/media/",
    )

    SUPPORTED = {"en", "es"}

    def __init__(self, get_response):
        self.get_response = get_response

    def _supported_language(self, value, default="en"):
        language = (value or "").lower().split("-")[0]
        return language if language in self.SUPPORTED else default

    def _resolve_language(self, request):
        path = getattr(request, "path", "") or ""

        if any(path.startswith(prefix) for prefix in self.TECHNICAL_ENGLISH_PREFIXES):
            return "en"

        user = getattr(request, "user", None)

        if user and user.is_authenticated and (user.is_superuser or user.is_staff):
            return self._supported_language(
                getattr(user, "preferred_language", "en")
            )

        if not user or not user.is_authenticated:
            # LocaleMiddleware already resolved the language cookie / browser
            # preference before this middleware executes.
            return self._supported_language(translation.get_language(), default="en")

        company = getattr(request, "current_company", None) or getattr(user, "id_company", None)
        company_language = getattr(company, "default_language", "en") if company else "en"

        # The separate contractor portal has a personal language preference.
        # Prefer the explicit portal session/cookie so the interface changes on
        # the very next request, then fall back to the saved account preference.
        if user_is_contractor_only(user):
            session_language = self._supported_language(
                request.session.get("contractor_portal_language"), default=""
            )
            cookie_language = self._supported_language(
                request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME), default=""
            )
            user_language = self._supported_language(
                getattr(user, "preferred_language", None), default=""
            )
            return (
                session_language
                or cookie_language
                or user_language
                or self._supported_language(company_language)
            )

        return self._supported_language(company_language)

    def __call__(self, request):
        language = self._resolve_language(request)
        request.LANGUAGE_CODE = language
        request.crm_language = language

        with translation.override(language):
            response = self.get_response(request)

        final_language = self._supported_language(
            getattr(request, "crm_language", language),
            default=language,
        )
        if response is not None and not response.has_header("Content-Language"):
            response["Content-Language"] = final_language

        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Resolve the company language for public estimate/contract links.

        Public customer links do not have an authenticated user, so their
        language is obtained from the document company without exposing any
        company data in the URL response.
        """
        resolver_match = getattr(request, "resolver_match", None)
        url_name = getattr(resolver_match, "url_name", "") if resolver_match else ""
        token = view_kwargs.get("token")

        if not token or not str(url_name).startswith("public_"):
            return None

        company = None

        if str(url_name).startswith("public_estimate_"):
            from apps.estimates.models import Estimate

            estimate = (
                Estimate.objects.select_related("id_company")
                .filter(public_token=token)
                .only("id_company", "id_company__default_language")
                .first()
            )
            company = estimate.id_company if estimate else None

        elif str(url_name).startswith("public_contract_"):
            from apps.contracts.models import Contract

            contract = (
                Contract.objects.select_related("id_company")
                .filter(public_token=token)
                .only("id_company", "id_company__default_language")
                .first()
            )
            company = contract.id_company if contract else None

        language = getattr(company, "default_language", "en") if company else "en"
        language = self._supported_language(language)

        request.current_company = company
        request.LANGUAGE_CODE = language
        request.crm_language = language
        translation.activate(language)
        return None


class ModuleAccessControlMiddleware:
    """
    Central guard for company CRM module permissions.

    Menu visibility is controlled by can_view, but this middleware also blocks
    direct URL access. Manage actions use can_create / can_edit / can_delete;
    sensitive workflow actions such as approve, reject, confirm, cancel and void
    use can_approve.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        path = getattr(request, "path", "") or ""

        if any(path.startswith(prefix) for prefix in SKIPPED_PATH_PREFIXES):
            return None

        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return None

        if user.is_superuser:
            return None

        resolver_match = getattr(request, "resolver_match", None)

        if not resolver_match:
            return None

        url_name = getattr(resolver_match, "url_name", "") or ""
        namespace = getattr(resolver_match, "namespace", "") or ""

        if any(url_name.startswith(prefix) for prefix in PUBLIC_ROUTE_PREFIXES):
            return None

        # Contractor accounts use a separate field-work module. Redirect old
        # administrative list/detail links so the two interfaces never share
        # templates or permission routing.
        if user_is_contractor_only(user) and request.method in SAFE_METHODS:
            normalized_namespace = _normalize_namespace(namespace)
            company = getattr(user, "id_company", None)
            company_slug = getattr(company, "slug", "")
            if company_slug and normalized_namespace == "inspections":
                if url_name == "inspection_list":
                    return redirect(f"/{company_slug}/field-work/inspections/")
                if url_name == "inspection_detail" and view_kwargs.get("id_assignment"):
                    return redirect(
                        f"/{company_slug}/field-work/inspections/{view_kwargs['id_assignment']}/"
                    )
            if company_slug and normalized_namespace == "projects":
                if url_name == "project_list":
                    return redirect(f"/{company_slug}/field-work/projects/")
                if url_name == "project_detail" and view_kwargs.get("id_project"):
                    return redirect(
                        f"/{company_slug}/field-work/projects/{view_kwargs['id_project']}/"
                    )

        if (
            user_is_contractor_only(user)
            and url_name in CONTRACTOR_SELF_SERVICE_ROUTE_NAMES
            and _normalize_namespace(namespace) in {"projects", "inspections"}
        ):
            return None

        module_name = _module_from_route(namespace, url_name, view_func)
        permission = _permission_from_route(url_name, request.method, view_func)

        if not module_name or not permission:
            return None

        if not user_has_module_permission(user, module_name, permission):
            return HttpResponseForbidden(translation.gettext("Permission denied."))

        return None
