from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator


from apps.companies.models import Company
from apps.core.template_permissions import PERMISSION_EDIT, user_can_module_action

from .forms import CompanyLanguageSettingsForm, SmtpSettingForm
from .services import get_or_create_smtp_setting, test_smtp_setting


def get_company_for_smtp_user(request, company_slug=None):
    """
    Returns the company that owns the SMTP configuration.

    This app is mounted in two ways:
    - /smtp-settings/
    - /<company_slug>/smtp-settings/

    Because of that, every view must accept company_slug and must never rely
    only on the logged user company. Superusers can open company workspaces,
    normal users can only open their own company workspace.
    """
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return None

    current_company = getattr(request, "current_company", None)

    if current_company:
        return current_company

    if company_slug:
        company = Company.objects.filter(slug=company_slug).first()

        if not company:
            return None

        if user.is_superuser:
            return company

        user_company = getattr(user, "id_company", None)

        if user_company and user_company.id_company == company.id_company:
            return company

        return None

    company = getattr(user, "id_company", None)

    if company:
        return company

    if user.is_superuser:
        return Company.objects.first()

    return None


def can_manage_company_smtp(user, company):
    """Only platform admins, company owners, or explicitly authorized roles may manage SMTP."""
    if not user or not user.is_authenticated or not company:
        return False
    if user.is_superuser:
        return True
    if getattr(user, "id_company_id", None) != company.id_company:
        return False
    if getattr(user, "is_company_owner", False):
        return True
    return user_can_module_action(user, "smtp_settings", PERMISSION_EDIT)


def get_smtp_form_url(company=None):
    if company and getattr(company, "slug", None):
        return f"/{company.slug}/smtp-settings/"

    return "/smtp-settings/"


def get_smtp_test_url(company=None):
    return f"{get_smtp_form_url(company)}test/"


def get_company_dashboard_url(company=None):
    if company and getattr(company, "slug", None):
        return f"/{company.slug}/dashboard/"

    return "/dashboard/"


def can_manage_company_language(user, company):
    if not user or not user.is_authenticated or not company:
        return False
    if user.is_superuser:
        return True
    if getattr(user, "id_company_id", None) != company.id_company:
        return False
    if getattr(user, "is_company_owner", False):
        return True
    role_name = getattr(getattr(user, "id_role", None), "name", "") or ""
    return role_name.strip().lower() in {"owner", "company owner"}


def build_smtp_context(company, form, smtp_setting, user=None, language_form=None):
    can_manage_language = can_manage_company_language(user, company)
    if language_form is None and can_manage_language:
        language_form = CompanyLanguageSettingsForm(
            initial={"default_language": company.default_language}
        )

    return {
        "page_title": "SMTP Settings",
        "form": form,
        "smtp_setting": smtp_setting,
        "company": company,
        "smtp_form_url": get_smtp_form_url(company),
        "smtp_test_url": get_smtp_test_url(company),
        "dashboard_url": get_company_dashboard_url(company),
        "can_manage_company_language": can_manage_language,
        "language_form": language_form,
    }


@method_decorator(never_cache, name="dispatch")
class SmtpSettingUpdateView(LoginRequiredMixin, View):
    template_name = "smtp_settings/form.html"
    login_url = "/login/"

    def get_company(self):
        return get_company_for_smtp_user(
            request=self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

    def get(self, request, *args, **kwargs):
        company = self.get_company()

        if not company:
            messages.error(
                request,
                "Your user does not have access to this company SMTP configuration.",
            )
            return redirect("/")

        if not can_manage_company_smtp(request.user, company):
            messages.error(request, "You do not have permission to manage SMTP settings.")
            return redirect(get_company_dashboard_url(company))

        smtp_setting = get_or_create_smtp_setting(company)
        form = SmtpSettingForm(instance=smtp_setting)

        return render(
            request,
            self.template_name,
            build_smtp_context(company, form, smtp_setting, user=request.user),
        )

    def post(self, request, *args, **kwargs):
        company = self.get_company()

        if not company:
            messages.error(
                request,
                "Your user does not have access to this company SMTP configuration.",
            )
            return redirect("/")

        if not can_manage_company_smtp(request.user, company):
            messages.error(request, "You do not have permission to manage SMTP settings.")
            return redirect(get_company_dashboard_url(company))

        if request.POST.get("settings_action") == "save_language":
            if not can_manage_company_language(request.user, company):
                messages.error(
                    request,
                    "Only the company owner can change the company language.",
                )
                return redirect(get_smtp_form_url(company))

            language_form = CompanyLanguageSettingsForm(request.POST)
            if language_form.is_valid():
                company.default_language = language_form.cleaned_data["default_language"]
                company.save(update_fields=["default_language"])
                messages.success(request, "Company language saved successfully.")
                return redirect(get_smtp_form_url(company))

            smtp_setting = get_or_create_smtp_setting(company)
            form = SmtpSettingForm(instance=smtp_setting)
            messages.error(request, "Please select a valid company language.")
            return render(
                request,
                self.template_name,
                build_smtp_context(
                    company,
                    form,
                    smtp_setting,
                    user=request.user,
                    language_form=language_form,
                ),
            )

        smtp_setting = get_or_create_smtp_setting(company)
        form = SmtpSettingForm(request.POST, instance=smtp_setting)

        if form.is_valid():
            smtp_setting = form.save(commit=False)
            smtp_setting.id_company = company
            smtp_setting.save()

            messages.success(request, "SMTP settings saved successfully.")
            return redirect(get_smtp_form_url(company))

        messages.error(request, "Please review the SMTP configuration.")

        return render(
            request,
            self.template_name,
            build_smtp_context(company, form, smtp_setting, user=request.user),
        )


@method_decorator(never_cache, name="dispatch")
class SmtpTestView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get_company(self):
        return get_company_for_smtp_user(
            request=self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

    def get(self, request, *args, **kwargs):
        company = self.get_company()

        if not company:
            messages.error(
                request,
                "Your user does not have access to this company SMTP configuration.",
            )
            return redirect("/")

        if not can_manage_company_smtp(request.user, company):
            messages.error(request, "You do not have permission to manage SMTP settings.")
            return redirect(get_company_dashboard_url(company))

        messages.info(
            request,
            "Use the Send Test Email button to run the SMTP test.",
        )
        return redirect(get_smtp_form_url(company))

    def post(self, request, *args, **kwargs):
        company = self.get_company()

        if not company:
            messages.error(
                request,
                "Your user does not have access to this company SMTP configuration.",
            )
            return redirect("/")

        if not can_manage_company_smtp(request.user, company):
            messages.error(request, "You do not have permission to manage SMTP settings.")
            return redirect(get_company_dashboard_url(company))

        smtp_setting = get_or_create_smtp_setting(company)

        recipient_email = (
            (request.POST.get("test_email") or "").strip()
            or getattr(request.user, "email", None)
        )

        if not recipient_email:
            messages.error(
                request,
                "Please enter an email address to send the test.",
            )
            return redirect(get_smtp_form_url(company))

        success, message = test_smtp_setting(
            smtp_setting=smtp_setting,
            recipient_email=recipient_email,
        )

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        return redirect(get_smtp_form_url(company))
