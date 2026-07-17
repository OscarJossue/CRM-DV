from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code
from apps.core.redirects import get_first_allowed_company_url, get_user_dashboard_url
from apps.core.tenant import user_is_global_admin
from apps.accounts.models.choices import PLATFORM_DASHBOARD
from apps.core.platform_permissions import PlatformPermissionRequiredMixin

def get_model_safe(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def count_safe(app_label, model_name, **filters):
    model = get_model_safe(app_label, model_name)

    if not model:
        return 0

    try:
        queryset = model.objects.all()

        if filters:
            queryset = queryset.filter(**filters)

        return queryset.count()
    except Exception:
        return 0


def sum_safe(app_label, model_name, field_name, **filters):
    model = get_model_safe(app_label, model_name)

    if not model:
        return Decimal("0.00")

    try:
        queryset = model.objects.all()

        if filters:
            queryset = queryset.filter(**filters)

        value = queryset.aggregate(total=Sum(field_name)).get("total")

        return value or Decimal("0.00")
    except Exception:
        return Decimal("0.00")


def list_safe(app_label, model_name, limit=10, order_by="-created_at", **filters):
    model = get_model_safe(app_label, model_name)

    if not model:
        return []

    try:
        queryset = model.objects.all()

        if filters:
            queryset = queryset.filter(**filters)

        if order_by:
            queryset = queryset.order_by(order_by)

        return list(queryset[:limit])
    except Exception:
        return []


def money(value):
    try:
        return f"${Decimal(value):,.2f}"
    except Exception:
        return "$0.00"





class PlatformAdminRequiredMixin(PlatformPermissionRequiredMixin):
    platform_module_name = PLATFORM_DASHBOARD


class PlatformDashboardView(LoginRequiredMixin, PlatformAdminRequiredMixin, TemplateView):
    template_name = "platform_core/dashboard.html"
    login_url = "/login/"

    def get_upcoming_renewals(self):
        PlatformSubscription = get_model_safe(
            "platform_subscriptions",
            "PlatformSubscription",
        )

        if not PlatformSubscription:
            return []

        today = timezone.localdate()
        limit_date = today + timedelta(days=30)

        try:
            return (
                PlatformSubscription.objects.select_related(
                    "id_company",
                    "id_plan",
                )
                .filter(
                    renewal_date__gte=today,
                    renewal_date__lte=limit_date,
                )
                .exclude(status__in=["canceled"])
                .order_by("renewal_date")[:8]
            )
        except Exception:
            return []

    def get_recent_payments(self):
        PlatformPayment = get_model_safe("platform_payments", "PlatformPayment")

        if not PlatformPayment:
            return []

        try:
            return (
                PlatformPayment.objects.select_related(
                    "id_company",
                    "id_document",
                    "received_by",
                )
                .order_by("-created_at")[:6]
            )
        except Exception:
            return []

    def get_recent_documents(self):
        PlatformDocument = get_model_safe("platform_documents", "PlatformDocument")

        if not PlatformDocument:
            return []

        try:
            return (
                PlatformDocument.objects.select_related(
                    "id_company",
                    "created_by",
                )
                .order_by("-created_at")[:6]
            )
        except Exception:
            return []

    def get_recent_audit_logs(self):
        possible_models = [
            "PlatformAuditLog",
            "PlatformAudit",
            "AuditLog",
        ]

        for model_name in possible_models:
            model = get_model_safe("platform_audit", model_name)

            if not model:
                continue

            try:
                return list(model.objects.all().order_by("-created_at")[:6])
            except Exception:
                return []

        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        active_companies = count_safe("companies", "Company", status="active")
        inactive_companies = count_safe("companies", "Company", status="inactive")

        active_subscriptions = count_safe(
            "platform_subscriptions",
            "PlatformSubscription",
            status="active",
        )
        trial_subscriptions = count_safe(
            "platform_subscriptions",
            "PlatformSubscription",
            status="trial",
        )
        expired_subscriptions = count_safe(
            "platform_subscriptions",
            "PlatformSubscription",
            status="expired",
        )
        suspended_subscriptions = count_safe(
            "platform_subscriptions",
            "PlatformSubscription",
            status="suspended",
        )
        canceled_subscriptions = count_safe(
            "platform_subscriptions",
            "PlatformSubscription",
            status="canceled",
        )

        total_paid_revenue = sum_safe(
            "platform_payments",
            "PlatformPayment",
            "amount",
            status="paid",
        )

        monthly_revenue = sum_safe(
            "platform_payments",
            "PlatformPayment",
            "amount",
            status="paid",
            payment_date__gte=month_start,
            payment_date__lte=today,
        )

        yearly_revenue = sum_safe(
            "platform_payments",
            "PlatformPayment",
            "amount",
            status="paid",
            payment_date__gte=year_start,
            payment_date__lte=today,
        )

        pending_payments = count_safe(
            "platform_payments",
            "PlatformPayment",
            status="pending",
        )

        paid_payments = count_safe(
            "platform_payments",
            "PlatformPayment",
            status="paid",
        )

        failed_emails = count_safe(
            "platform_email",
            "PlatformEmailLog",
            status="failed",
        )

        sent_emails = count_safe(
            "platform_email",
            "PlatformEmailLog",
            status="sent",
        )

        context["page_title"] = "CRM Admin Dashboard"

        context["dashboard_cards"] = [
            {
                "label": "Companies",
                "value": count_safe("companies", "Company"),
                "text": "Total companies registered in the SaaS platform.",
            },
            {
                "label": "Active Companies",
                "value": active_companies,
                "text": "Companies currently enabled for CRM access.",
            },
            {
                "label": "Inactive Companies",
                "value": inactive_companies,
                "text": "Companies blocked or inactive due to subscription status.",
            },
            {
                "label": "Plans",
                "value": count_safe("platform_plans", "PlatformPlan"),
                "text": "SaaS plans available for company subscriptions.",
            },
            {
                "label": "Active Subscriptions",
                "value": active_subscriptions,
                "text": "Subscriptions currently active.",
            },
            {
                "label": "Trial Subscriptions",
                "value": trial_subscriptions,
                "text": "Companies currently running under trial access.",
            },
            {
                "label": "Expired Subscriptions",
                "value": expired_subscriptions,
                "text": "Subscriptions that need renewal review.",
            },
            {
                "label": "Suspended",
                "value": suspended_subscriptions,
                "text": "Subscriptions manually suspended by CEO MARKETING.",
            },
            {
                "label": "Canceled",
                "value": canceled_subscriptions,
                "text": "Subscriptions canceled and no longer active.",
            },
            {
                "label": "Proformas",
                "value": count_safe(
                    "platform_documents",
                    "PlatformDocument",
                    document_type="proforma",
                ),
                "text": "SaaS proformas issued to companies.",
            },
            {
                "label": "Invoices",
                "value": count_safe(
                    "platform_documents",
                    "PlatformDocument",
                    document_type="invoice",
                ),
                "text": "SaaS invoices generated for companies.",
            },
            {
                "label": "Pending Payments",
                "value": pending_payments,
                "text": "Payments waiting for confirmation.",
            },
            {
                "label": "Paid Payments",
                "value": paid_payments,
                "text": "Payments marked as paid.",
            },
            {
                "label": "Monthly Revenue",
                "value": money(monthly_revenue),
                "text": "Paid SaaS revenue collected this month.",
            },
            {
                "label": "Yearly Revenue",
                "value": money(yearly_revenue),
                "text": "Paid SaaS revenue collected this year.",
            },
            {
                "label": "Total Paid Revenue",
                "value": money(total_paid_revenue),
                "text": "Total paid SaaS payments registered in the platform.",
            },
            {
                "label": "Sent Emails",
                "value": sent_emails,
                "text": "Emails sent through the platform SMTP system.",
            },
            {
                "label": "Failed Emails",
                "value": failed_emails,
                "text": "Emails that failed and need review.",
            },
            {
                "label": "Calendar Events",
                "value": count_safe("platform_calendar", "PlatformCalendarEvent"),
                "text": "Internal SaaS calendar events and renewal follow-ups.",
            },
            {
                "label": "Audit Logs",
                "value": count_safe("platform_audit", "PlatformAuditLog"),
                "text": "Administrative actions recorded in the SaaS audit module.",
            },
        ]

        context["upcoming_renewals"] = self.get_upcoming_renewals()
        context["recent_payments"] = self.get_recent_payments()
        context["recent_documents"] = self.get_recent_documents()
        context["recent_audit_logs"] = self.get_recent_audit_logs()

        return context


class AccountSuspendedView(LoginRequiredMixin, TemplateView):
    template_name = "platform_core/account_suspended.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        # This page is reserved exclusively for a real account/company block.
        # Previously, an active tenant with no permitted modules was sent here,
        # which falsely presented an active company as subscription-suspended.
        if get_user_runtime_access_code(request.user) == ACCESS_ALLOWED:
            target = get_first_allowed_company_url(request.user)
            if target:
                return redirect(target)
            return redirect(reverse("platform_core:no_permissions"))

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = getattr(self.request.user, "id_company", None)

        context["page_title"] = "Account Suspended"
        context["company"] = company
        context["access_code"] = get_user_runtime_access_code(self.request.user)

        return context


class NoPermissionsView(LoginRequiredMixin, TemplateView):
    template_name = "platform_core/no_permissions.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        access_code = get_user_runtime_access_code(request.user)
        if access_code != ACCESS_ALLOWED:
            return redirect(reverse("platform_core:account_suspended"))

        target = get_first_allowed_company_url(request.user)
        if target:
            return redirect(target)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["page_title"] = "No Modules Assigned"
        context["company"] = getattr(user, "id_company", None)
        context["role"] = getattr(user, "id_role", None)
        return context


class SmartHomeRedirectView(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login/")

        return redirect(get_user_dashboard_url(request.user))