from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from apps.companies.models import Company
from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code
from apps.core.tenant import user_is_global_admin


class PlatformSubscriptionAccessMiddleware:
    """
    Controls access for:
    - CEO MARKETING root superusers.
    - CEO MARKETING internal platform staff.
    - Company workspace users.

    Also keeps develoverps company CRM templates working by resetting
    request.current_app so templates can use legacy URLs like:
    {% url 'clients:client_create' %}
    """

    EXEMPT_PREFIXES = (
        "/admin/",
        "/crm/",
        "/api/platform/",
        "/api/companies/",
        "/login/",
        "/accounts/logout/",
        "/logout/",
        "/account-suspended/",
        "/media/",
        "/static/",
        "/metrics",
        "/health",
        "/favicon.ico",
        "/dashboard-metrics/",
        "/system-monitor/",
    )

    LEGACY_COMPANY_PREFIX_MAP = {
        "clients": "clients",
        "leads": "leads",
        "opportunities": "opportunities",
        "projects": "projects",
        "inspections": "inspections",
        "evidence": "evidence",
        "supervision": "supervision",
        "calendar-events": "calendar",
        "estimates": "estimates",
        "invoices": "invoices",
        "payments": "payments",
        "contracts": "contracts",
        "reports": "reports",
        "smtp-settings": "smtp-settings",
        "employees": "employees",
        "notifications": "notifications",
        "system-logs": "system-logs",
        "user-activities": "system-logs",
        "users": "users",
        "roles": "roles",
        "permissions": "permissions",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Important:
        # Django templates use request.resolver_match.namespace as current_app
        # when request.current_app does not exist. Inside /company/clients/,
        # that makes {% url 'clients:client_create' %} try to reverse the
        # company namespaced route and fail because company_slug is missing.
        #
        # By setting current_app to None, develoverps templates can keep using
        # their original URL names without passing company_slug.
        request.current_app = None

        if self.should_skip(request):
            return self.get_response(request)

        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return self.get_response(request)

        if user_is_global_admin(user):
            return self.get_response(request)

        if self.user_is_platform_staff(user):
            if request.path == "/":
                return redirect(reverse("platform_core:dashboard"))

            return self.get_response(request)

        legacy_redirect_url = self.get_legacy_company_redirect_url(request)

        if legacy_redirect_url:
            return redirect(legacy_redirect_url)

        company = getattr(user, "id_company", None)

        request.current_company = company

        # Runtime requests are read-only with respect to company access.
        # Never call sync_company_access() here: doing so made a normal login
        # silently rewrite an explicitly active company to inactive.
        if get_user_runtime_access_code(user) != ACCESS_ALLOWED:
            if self.is_api_request(request):
                return JsonResponse(
                    {
                        "detail": "Company access is suspended. Please contact CEO Marketing USA.",
                        "code": "company_subscription_inactive",
                    },
                    status=403,
                )

            return redirect(reverse("platform_core:account_suspended"))

        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.current_app = None

        company_slug = view_kwargs.get("company_slug")

        if not company_slug:
            return None

        user = getattr(request, "user", None)

        if user and user.is_authenticated and user_is_global_admin(user):
            company = Company.objects.filter(slug=company_slug).first()

            if company:
                request.current_company = company

            return None

        if user and user.is_authenticated and self.user_is_platform_staff(user):
            return redirect(reverse("platform_core:dashboard"))

        company = Company.objects.filter(slug=company_slug).first()

        if not company:
            if user and user.is_authenticated:
                user_company = getattr(user, "id_company", None)

                if user_company and getattr(user_company, "slug", None):
                    return redirect(f"/{user_company.slug}/dashboard/")

            if self.is_api_request(request):
                return JsonResponse(
                    {
                        "detail": "Company workspace not found.",
                        "code": "company_workspace_not_found",
                    },
                    status=404,
                )

            return redirect(reverse("platform_core:dashboard"))

        request.current_company = company

        if not user or not user.is_authenticated:
            return None

        user_company = getattr(user, "id_company", None)

        if not user_company:
            return redirect(reverse("platform_core:account_suspended"))

        if user_company.id_company != company.id_company:
            return redirect(f"/{user_company.slug}/dashboard/")

        request.current_company = company

        if get_user_runtime_access_code(user) != ACCESS_ALLOWED:
            if self.is_api_request(request):
                return JsonResponse(
                    {
                        "detail": "Company access is suspended. Please contact CEO Marketing USA.",
                        "code": "company_subscription_inactive",
                    },
                    status=403,
                )

            return redirect(reverse("platform_core:account_suspended"))

        return None

    def get_legacy_company_redirect_url(self, request):
        path = (request.path or "").strip("/")

        if not path:
            return None

        parts = path.split("/")
        first_part = parts[0]

        target_prefix = self.LEGACY_COMPANY_PREFIX_MAP.get(first_part)

        if not target_prefix:
            return None

        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return None

        if user_is_global_admin(user):
            return reverse("platform_core:dashboard")

        if self.user_is_platform_staff(user):
            return reverse("platform_core:dashboard")

        company = getattr(user, "id_company", None)

        if not company or not getattr(company, "slug", None):
            return reverse("platform_core:account_suspended")

        remaining_parts = parts[1:]
        remaining_path = "/".join(remaining_parts)

        if remaining_path:
            return f"/{company.slug}/{target_prefix}/{remaining_path}/"

        return f"/{company.slug}/{target_prefix}/"

    def should_skip(self, request):
        path = request.path or ""

        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def is_api_request(self, request):
        path = request.path or ""

        if path.startswith("/api/"):
            return True

        requested_with = request.headers.get("x-requested-with", "")
        accept = request.headers.get("accept", "")

        return requested_with.lower() == "xmlhttprequest" or "application/json" in accept

    def user_is_platform_staff(self, user):
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
            and not user.is_superuser
        )