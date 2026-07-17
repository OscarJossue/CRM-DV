from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.audit.services import log_system_action
from apps.companies.models import Company
from apps.core.platform_permissions import user_can_access_platform
from apps.platform_audit.services import log_platform_action

from .forms import CompanyLanguageForm, PlatformLanguageForm


SUPPORTED_LANGUAGES = {"en", "es"}
LANGUAGE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _safe_next_url(request, fallback):
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _language_response(request, language, redirect_to):
    request.LANGUAGE_CODE = language
    request.crm_language = language
    translation.activate(language)

    response = redirect(redirect_to)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        path="/",
        secure=request.is_secure(),
        httponly=False,
        samesite="Lax",
    )
    response["Content-Language"] = language
    return response


def get_request_company(request, company_slug=None):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return None

    if user.is_superuser or request.path.startswith("/crm/"):
        return None

    current_company = getattr(request, "current_company", None)
    if current_company:
        return current_company

    if company_slug:
        company = Company.objects.filter(slug=company_slug).first()
        if not company:
            return None
        if getattr(user, "id_company_id", None) == company.id_company:
            return company
        return None

    return getattr(user, "id_company", None)


def is_company_owner(user, company):
    if not user or not user.is_authenticated or not company:
        return False
    if user.is_superuser:
        return False
    if getattr(user, "id_company_id", None) != company.id_company:
        return False
    if getattr(user, "is_company_owner", False):
        return True
    role_name = getattr(getattr(user, "id_role", None), "name", "") or ""
    return role_name.strip().lower() == "owner"


class PublicLanguageSwitchView(View):
    """Select the login/interface language without requiring authentication."""

    http_method_names = ["post", "options"]

    def post(self, request, *args, **kwargs):
        language = (request.POST.get("language") or "").strip().lower()
        fallback = reverse("login")
        redirect_to = _safe_next_url(request, fallback)

        if language not in SUPPORTED_LANGUAGES:
            language = "en"

        user = getattr(request, "user", None)
        if user and user.is_authenticated and user_can_access_platform(user):
            if getattr(user, "preferred_language", "en") != language:
                user.preferred_language = language
                user.save(update_fields=["preferred_language"])

        return _language_response(request, language, redirect_to)


class PlatformLanguageView(LoginRequiredMixin, View):
    template_name = "languages/platform_settings.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_can_access_platform(request.user):
            return HttpResponseForbidden(
                "Only platform administrators can manage this language preference."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_current_language(self):
        current = getattr(self.request.user, "preferred_language", "en") or "en"
        return current if current in SUPPORTED_LANGUAGES else "en"

    def get(self, request, *args, **kwargs):
        current = self.get_current_language()
        form = PlatformLanguageForm(initial={"language": current})
        return render(
            request,
            self.template_name,
            {
                "page_title": "Language & Region",
                "page_subtitle": "Choose the language used in your CEO MARKETING administration console.",
                "form": form,
                "current_language": current,
            },
        )

    def post(self, request, *args, **kwargs):
        form = PlatformLanguageForm(request.POST)
        current = self.get_current_language()

        if not form.is_valid():
            messages.error(request, "Please select a valid language.")
            return render(
                request,
                self.template_name,
                {
                    "page_title": "Language & Region",
                    "page_subtitle": "Choose the language used in your CEO MARKETING administration console.",
                    "form": form,
                    "current_language": current,
                },
            )

        next_language = form.cleaned_data["language"]
        previous_language = current

        if previous_language != next_language:
            request.user.preferred_language = next_language
            request.user.save(update_fields=["preferred_language"])
            log_platform_action(
                user=request.user,
                module_name="platform_language",
                action="update",
                object_id=request.user.pk,
                object_label=request.user.email,
                description=(
                    f"Platform language updated from {previous_language} "
                    f"to {next_language}."
                ),
                request=request,
                metadata={
                    "previous_language": previous_language,
                    "new_language": next_language,
                },
            )

        with translation.override(next_language):
            messages.success(request, "Platform language updated successfully.")

        redirect_to = _safe_next_url(
            request,
            reverse("platform_languages:settings"),
        )
        return _language_response(request, next_language, redirect_to)


class CompanyLanguageView(LoginRequiredMixin, View):
    template_name = "languages/settings.html"
    login_url = "/login/"

    def get_company(self):
        return get_request_company(
            self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.company = self.get_company()
        if not is_company_owner(request.user, self.company):
            return HttpResponseForbidden(
                "Only the company Owner can manage workspace languages."
            )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        current = getattr(self.company, "default_language", "en") or "en"
        form = CompanyLanguageForm(initial={"language": current})
        return render(
            request,
            self.template_name,
            {
                "page_title": "Languages",
                "page_subtitle": "Choose the language used across this company workspace.",
                "form": form,
                "company": self.company,
                "current_language": current,
            },
        )

    def post(self, request, *args, **kwargs):
        form = CompanyLanguageForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please select a valid language.")
            return render(
                request,
                self.template_name,
                {
                    "page_title": "Languages",
                    "page_subtitle": "Choose the language used across this company workspace.",
                    "form": form,
                    "company": self.company,
                    "current_language": getattr(self.company, "default_language", "en"),
                },
            )

        next_language = form.cleaned_data["language"]
        if next_language not in SUPPORTED_LANGUAGES:
            messages.error(request, "Please select a valid language.")
            return redirect(self.get_success_url())

        previous_language = getattr(self.company, "default_language", "en") or "en"

        if previous_language != next_language:
            self.company.default_language = next_language
            self.company.save(update_fields=["default_language"])
            log_system_action(
                user=request.user,
                company=self.company,
                module="languages",
                action=f"workspace_language_updated:{previous_language}->{next_language}",
                request=request,
            )

        request.LANGUAGE_CODE = next_language
        request.crm_language = next_language
        with translation.override(next_language):
            messages.success(request, "Workspace language updated successfully.")

        return redirect(self.get_success_url())

    def get_success_url(self):
        if self.company and self.company.slug:
            return f"/{self.company.slug}/languages/"
        return "/languages/"
