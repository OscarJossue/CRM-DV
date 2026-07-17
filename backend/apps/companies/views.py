from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView, UpdateView
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from apps.platform_subscriptions.models.choices import SUBSCRIPTION_ACTIVE, SUBSCRIPTION_SUSPENDED
from apps.platform_subscriptions.services import (
    calculate_plan_renewal_date,
    reactivate_platform_subscription,
    sync_company_access,
    sync_subscription_status,
)

from apps.accounts.models import UserAccount
from apps.core.mixins import TenantModelViewSet
from apps.core.platform_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)
from apps.platform_users.constants import PLATFORM_MODULE_COMPANIES
from apps.platform_documents.models import PlatformDocument
from apps.platform_payments.models import PlatformPayment
from apps.platform_subscriptions.models import PlatformSubscription

from .forms import CompanyForm, CompanyProvisioningForm
from .models import Company
from .serializers import CompanySerializer
from .services import (
    company_activate,
    company_deactivate,
    get_company_plan_code_from_platform_plan,
    provision_company_with_admin,
)
from .temp_uploads import (
    apply_temp_company_logo_to_instance,
    get_temp_company_logo_context,
    save_company_logo_to_temp,
)

from apps.platform_audit.services import log_platform_action
from apps.platform_audit.models.choices import (
    PLATFORM_AUDIT_ACTION_ACTIVATE,
    PLATFORM_AUDIT_ACTION_CREATE,
    PLATFORM_AUDIT_ACTION_DEACTIVATE,
    PLATFORM_AUDIT_ACTION_UPDATE,
)


class PlatformCompaniesPermissionMixin(PlatformPermissionRequiredMixin):
    login_url = "/login/"
    raise_exception = True
    platform_module_name = PLATFORM_MODULE_COMPANIES
    platform_permission_required = PERMISSION_VIEW


class CompanyTemporaryLogoMixin:
    def get_logo_temp_token(self):
        return (
            getattr(self, "logo_temp_token", "")
            or self.request.POST.get("logo_temp_token", "")
            or ""
        ).strip()

    def capture_logo_temp_token_for_invalid_form(self, form):
        current_token = (self.request.POST.get("logo_temp_token", "") or "").strip()
        uploaded_logo = self.request.FILES.get("logo")

        if uploaded_logo and "logo" not in form.errors:
            current_token = save_company_logo_to_temp(uploaded_logo) or current_token

        self.logo_temp_token = current_token

        return current_token

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        logo_temp_token = self.get_logo_temp_token()
        context.update(get_temp_company_logo_context(logo_temp_token))

        return context

    def apply_temp_logo_if_needed(self, company):
        if not company:
            return False

        if self.request.FILES.get("logo"):
            return False

        if self.request.POST.get("logo-clear") == "on":
            return False

        logo_temp_token = self.get_logo_temp_token()

        if not logo_temp_token:
            return False

        return apply_temp_company_logo_to_instance(
            company,
            logo_temp_token,
            save=True,
        )


def get_company_owner(company):
    owner = (
        UserAccount.objects.select_related("id_role", "id_company")
        .filter(id_company=company, is_company_owner=True)
        .order_by("id_user")
        .first()
    )

    if owner:
        return owner

    return (
        UserAccount.objects.select_related("id_role", "id_company")
        .filter(id_company=company, id_role__name__iexact="Owner")
        .order_by("id_user")
        .first()
    )


def get_current_subscription(company):
    return (
        PlatformSubscription.objects.select_related("id_plan", "id_company")
        .filter(id_company=company)
        .order_by("-created_at")
        .first()
    )


def sync_company_plan_and_subscription_from_form(company, form):
    selected_plan = form.cleaned_data.get("id_plan")
    subscription_notes = form.cleaned_data.get("subscription_notes")
    start_date = form.cleaned_data.get("subscription_start_date") or timezone.localdate()
    renewal_date = form.cleaned_data.get("subscription_renewal_date")

    if not company or not selected_plan:
        return None

    if not renewal_date:
        renewal_date = calculate_plan_renewal_date(
            selected_plan,
            start_date=start_date,
        )

    company.plan = get_company_plan_code_from_platform_plan(selected_plan)
    company.user_limit = selected_plan.max_users or 1
    company.save(update_fields=["plan", "user_limit"])

    subscription = (
        PlatformSubscription.objects.select_for_update()
        .select_related("id_company", "id_plan")
        .filter(id_company=company)
        .order_by("-created_at")
        .first()
    )

    today = timezone.localdate()

    if subscription:
        subscription.id_plan_id = selected_plan.id_plan
        subscription.start_date = start_date
        subscription.renewal_date = renewal_date
        subscription.notes = subscription_notes

        if renewal_date and renewal_date >= today:
            subscription.status = SUBSCRIPTION_ACTIVE
            subscription.end_date = None

        subscription.save(
            update_fields=[
                "id_plan",
                "start_date",
                "renewal_date",
                "notes",
                "status",
                "end_date",
            ]
        )
    else:
        subscription = PlatformSubscription.objects.create(
            id_company=company,
            id_plan=selected_plan,
            status=SUBSCRIPTION_ACTIVE,
            start_date=start_date,
            renewal_date=renewal_date,
            notes=subscription_notes,
        )

    sync_subscription_status(subscription)

    subscription.refresh_from_db()

    sync_company_access(company)

    company.refresh_from_db()

    return subscription

class CompanyListView(LoginRequiredMixin, PlatformCompaniesPermissionMixin, ListView):
    platform_permission_required = PERMISSION_VIEW

    template_name = "companies/list.html"
    context_object_name = "companies"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = Company.objects.all().order_by("name")

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()

        if q:
            queryset = queryset.filter(name__icontains=q)

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        companies = context["companies"]
        rows = []

        for company in companies:
            rows.append(
                {
                    "company": company,
                    "owner": get_company_owner(company),
                    "subscription": get_current_subscription(company),
                }
            )

        context["page_title"] = "Companies"
        context["company_rows"] = rows
        context["q"] = self.request.GET.get("q", "").strip()
        context["status_filter"] = self.request.GET.get("status", "").strip()
        context["total_companies"] = Company.objects.count()
        context["active_companies"] = Company.objects.filter(status="active").count()
        context["inactive_companies"] = Company.objects.filter(status="inactive").count()

        context["can_view_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_VIEW,
        )
        context["can_create_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_CREATE,
        )
        context["can_edit_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_EDIT,
        )
        context["can_approve_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_APPROVE,
        )
        context["can_manage_companies"] = (
            context["can_create_companies"]
            or context["can_edit_companies"]
            or context["can_approve_companies"]
        )
        context["is_global_admin"] = True

        return context


class CompanyDetailView(LoginRequiredMixin, PlatformCompaniesPermissionMixin, DetailView):
    platform_permission_required = PERMISSION_VIEW

    model = Company
    template_name = "companies/detail.html"
    context_object_name = "company"
    pk_url_kwarg = "id_company"
    login_url = "/login/"

    def get_queryset(self):
        return Company.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = self.object

        context["page_title"] = "Company Detail"
        context["owner_user"] = get_company_owner(company)
        context["users"] = UserAccount.objects.select_related("id_role").filter(id_company=company).order_by("first_name")
        context["subscriptions"] = PlatformSubscription.objects.select_related("id_plan").filter(id_company=company)
        context["current_subscription"] = get_current_subscription(company)
        context["documents"] = PlatformDocument.objects.filter(id_company=company).order_by("-created_at")[:8]
        context["payments"] = PlatformPayment.objects.filter(id_company=company).order_by("-created_at")[:8]
        context["documents_count"] = PlatformDocument.objects.filter(id_company=company).count()
        context["payments_count"] = PlatformPayment.objects.filter(id_company=company).count()

        context["can_create_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_CREATE,
        )
        context["can_edit_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_EDIT,
        )
        context["can_approve_companies"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_APPROVE,
        )
        context["can_manage_companies"] = (
            context["can_create_companies"]
            or context["can_edit_companies"]
            or context["can_approve_companies"]
        )
        context["is_global_admin"] = True

        return context


class CompanyCreateView(CompanyTemporaryLogoMixin, LoginRequiredMixin, PlatformCompaniesPermissionMixin, FormView):
    """Single atomic company provisioning flow rendered as two windows."""

    platform_permission_required = PERMISSION_CREATE
    form_class = CompanyProvisioningForm
    template_name = "companies/create_wizard.html"
    login_url = "/login/"

    def form_valid(self, form):
        try:
            with transaction.atomic():
                result = provision_company_with_admin(
                    company_data={
                        "name": form.cleaned_data.get("name"),
                        "legal_name": form.cleaned_data.get("legal_name"),
                        "email": form.cleaned_data.get("email"),
                        "phone": form.cleaned_data.get("phone"),
                        "address": form.cleaned_data.get("address"),
                        "city": form.cleaned_data.get("city"),
                        "state": form.cleaned_data.get("state"),
                        "country": form.cleaned_data.get("country"),
                        "logo": form.cleaned_data.get("logo"),
                        "description": form.cleaned_data.get("description"),
                    },
                    admin_data={
                        "first_name": form.cleaned_data.get("admin_first_name"),
                        "last_name": form.cleaned_data.get("admin_last_name"),
                        "email": form.cleaned_data.get("admin_email"),
                        "phone": form.cleaned_data.get("admin_phone"),
                        "password": form.cleaned_data.get("password1"),
                    },
                    subscription_data={
                        "id_plan": form.cleaned_data.get("id_plan"),
                        "start_date": form.cleaned_data.get("start_date"),
                        "renewal_date": form.cleaned_data.get("renewal_date"),
                    },
                )

                company = result["company"]
                administrator = result["administrator"]
                subscription = result["subscription"]
                self.object = company
                self.apply_temp_logo_if_needed(company)

                log_platform_action(
                    user=self.request.user,
                    company=company,
                    module_name="companies",
                    action=PLATFORM_AUDIT_ACTION_CREATE,
                    object_id=company.id_company,
                    object_label=company.name,
                    description=f"Company provisioned with administrator: {company.name}",
                    request=self.request,
                    metadata={
                        "company_slug": company.slug,
                        "company_status": company.status,
                        "administrator_user_id": administrator.id_user,
                        "administrator_email": administrator.email,
                        "subscription_id": subscription.id_subscription,
                        "plan_id": subscription.id_plan_id,
                        "renewal_date": subscription.renewal_date.isoformat() if subscription.renewal_date else None,
                    },
                )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Company created successfully. Administrator login: {administrator.email}.",
        )
        return redirect("companies:company_detail", id_company=company.id_company)

    def form_invalid(self, form):
        self.capture_logo_temp_token_for_invalid_form(form)
        messages.error(self.request, "Please review the highlighted fields.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        context["page_title"] = "Create Company"
        context["form_title"] = "Create Company"
        context["submit_label"] = "Create Company and Administrator"
        context["initial_step"] = form.first_error_step() if form and form.is_bound else 1
        return context



class CompanyUpdateView(CompanyTemporaryLogoMixin, LoginRequiredMixin, PlatformCompaniesPermissionMixin, UpdateView):
    platform_permission_required = PERMISSION_EDIT

    model = Company
    form_class = CompanyForm
    template_name = "companies/form.html"
    context_object_name = "company"
    pk_url_kwarg = "id_company"
    login_url = "/login/"

    def get_queryset(self):
        return Company.objects.all()

    def get_success_url(self):
        return reverse_lazy(
            "companies:company_detail",
            kwargs={"id_company": self.object.id_company},
        )

    def form_valid(self, form):
        previous_subscription = get_current_subscription(self.object)

        previous_metadata = {
            "company_status": self.object.status,
            "company_user_limit": self.object.user_limit,
            "subscription_id": previous_subscription.id_subscription if previous_subscription else None,
            "plan_id": previous_subscription.id_plan_id if previous_subscription else None,
            "plan_name": previous_subscription.id_plan.name if previous_subscription and previous_subscription.id_plan else None,
            "renewal_date": previous_subscription.renewal_date.isoformat() if previous_subscription and previous_subscription.renewal_date else None,
        }

        with transaction.atomic():
            company = form.save(commit=False)
            company.save()

            self.object = company

            self.apply_temp_logo_if_needed(self.object)

            subscription = sync_company_plan_and_subscription_from_form(
                self.object,
                form,
            )

            administrator_result = form.save_company_administrator(self.object)
            owner_password_changed = administrator_result["password_changed"]

            log_platform_action(
                user=self.request.user,
                company=self.object,
                module_name="companies",
                action=PLATFORM_AUDIT_ACTION_UPDATE,
                object_id=self.object.id_company,
                object_label=self.object.name,
                description=f"Company updated: {self.object.name}",
                request=self.request,
                metadata={
                    "previous": previous_metadata,
                    "current": {
                        "company_slug": self.object.slug,
                        "company_status": self.object.status,
                        "plan_id": subscription.id_plan_id if subscription else None,
                        "plan_name": subscription.id_plan.name if subscription and subscription.id_plan else None,
                        "subscription_id": subscription.id_subscription if subscription else None,
                        "renewal_date": subscription.renewal_date.isoformat() if subscription and subscription.renewal_date else None,
                        "user_limit_from_plan": self.object.user_limit,
                        "owner_password_changed": owner_password_changed,
                    },
                },
            )

        success_message = f"Company updated. Plan: {subscription.id_plan.name if subscription else 'No plan'}."

        if administrator_result["created"]:
            success_message += " Company administrator created successfully."
        elif owner_password_changed:
            success_message += " Administrator password updated successfully."

        messages.success(self.request, success_message)

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        self.capture_logo_temp_token_for_invalid_form(form)
        messages.error(self.request, "Please review the company form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Company"
        context["form_title"] = "Edit Company"
        context["submit_label"] = "Update Company"
        return context


@require_POST
def company_activate_view(request, id_company):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_COMPANIES,
        PERMISSION_APPROVE,
    ):
        raise DjangoPermissionDenied("You do not have permission to activate companies.")

    company = get_object_or_404(Company, id_company=id_company)

    subscription = get_current_subscription(company)

    with transaction.atomic():
        if subscription:
            # Reactivation renews the billing cycle and synchronizes access.
            reactivate_platform_subscription(
                subscription,
                force_new_cycle=True,
            )
        else:
            # A company without a subscription record can still be explicitly
            # activated by the platform administrator. Do not immediately call
            # sync_company_access(), because that would undo the activation.
            company_activate(company)

        company.refresh_from_db()

    messages.success(request, "Company reactivated successfully.")

    log_platform_action(
        user=request.user,
        company=company,
        module_name="companies",
        action=PLATFORM_AUDIT_ACTION_ACTIVATE,
        object_id=company.id_company,
        object_label=company.name,
        description=f"Company reactivated: {company.name}",
        request=request,
        metadata={
            "company_slug": company.slug,
            "company_status": company.status,
            "subscription_id": subscription.id_subscription if subscription else None,
            "renewal_date": subscription.renewal_date.isoformat() if subscription and subscription.renewal_date else None,
        },
    )

    return redirect("companies:company_detail", id_company=company.id_company)


@require_POST
def company_deactivate_view(request, id_company):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_COMPANIES,
        PERMISSION_APPROVE,
    ):
        raise DjangoPermissionDenied("You do not have permission to deactivate companies.")

    company = get_object_or_404(Company, id_company=id_company)
    subscription = get_current_subscription(company)

    with transaction.atomic():
        if subscription:
            subscription.status = SUBSCRIPTION_SUSPENDED
            subscription.save(update_fields=["status"])

        company_deactivate(company)
        company.refresh_from_db()

    messages.success(request, "Company deactivated successfully.")

    log_platform_action(
        user=request.user,
        company=company,
        module_name="companies",
        action=PLATFORM_AUDIT_ACTION_DEACTIVATE,
        object_id=company.id_company,
        object_label=company.name,
        description=f"Company deactivated: {company.name}",
        request=request,
        metadata={
            "company_slug": company.slug,
            "company_status": company.status,
            "subscription_id": subscription.id_subscription if subscription else None,
            "subscription_status": subscription.status if subscription else None,
        },
    )

    return redirect("companies:company_detail", id_company=company.id_company)


class CompanyViewSet(TenantModelViewSet):
    module_name = "companies"
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    tenant_filter_path = None
    tenant_create_field = None

    def get_queryset(self):
        if not user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_VIEW,
        ):
            return Company.objects.none()

        return Company.objects.all().order_by("name")

    def perform_create(self, serializer):
        if not user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_CREATE,
        ):
            raise DRFPermissionDenied("You do not have permission to create companies.")

        serializer.save()

    def perform_update(self, serializer):
        if not user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_EDIT,
        ):
            raise DRFPermissionDenied("You do not have permission to update companies.")

        serializer.save()

    def perform_destroy(self, instance):
        if not user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_DELETE,
        ):
            raise DRFPermissionDenied("You do not have permission to delete companies.")

        instance.delete()