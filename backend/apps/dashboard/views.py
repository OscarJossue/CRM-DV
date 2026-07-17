from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.models import UserAccount
from apps.calendar_events.models import CalendarEvent
from apps.calendar_events.services import get_company_calendar_items
from apps.clients.models import Client
from apps.companies.models import Company
from apps.core.tenant import user_is_global_admin
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_VIEW,
    user_can_module_action,
)
from apps.employees.models import Employee
from apps.estimates.models import Estimate
from apps.inspections.models import Inspection, InspectionAssignment
from apps.invoices.models import Invoice
from apps.invoices.models.choices import INVOICE_PAYMENT_STATUS_PAID, INVOICE_STATUS_VOID
from apps.opportunities.models import Lead
from apps.payments.models import Payment
from apps.payments.models.choices import PAYMENT_CONFIRMED_STATUSES
from apps.projects.models import Project


def model_has_field(model, field_name):
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def order_queryset_safe(queryset, preferred_fields):
    model = queryset.model

    for field_name in preferred_fields:
        clean_field_name = field_name.replace("-", "")

        if model_has_field(model, clean_field_name):
            return queryset.order_by(field_name)

    return queryset


class DashboardHomeView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    module_name = "dashboard"
    permission_required = PERMISSION_VIEW
    template_name = "dashboard/dashboard_home.html"
    login_url = "/login/"

    def get_company_from_request(self):
        company_slug = self.kwargs.get("company_slug")

        if company_slug:
            company = Company.objects.filter(slug=company_slug).first()

            if not company:
                return None

            user = self.request.user

            if user_is_global_admin(user):
                return company

            user_company = getattr(user, "id_company", None)

            if not user_company:
                raise PermissionDenied("User does not have a company assigned.")

            if user_company.id_company != company.id_company:
                raise PermissionDenied("You do not have access to this company dashboard.")

            return company

        if user_is_global_admin(self.request.user):
            return None

        return getattr(self.request.user, "id_company", None)

    def get_total_payments_for_company(self, company):
        total_payments = Payment.objects.filter(
            id_company=company,
            status__in=PAYMENT_CONFIRMED_STATUSES,
        ).aggregate(total=Sum("amount")).get("total")

        return total_payments or Decimal("0.00")

    def dispatch(self, request, *args, **kwargs):
        company = self.get_company_from_request()

        if not company:
            if user_is_global_admin(request.user):
                return redirect("platform_core:dashboard")

            return redirect("platform_core:account_suspended")

        self.company = company

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = self.company
        today = timezone.localdate()

        modules = [
            "users",
            "employees",
            "clients",
            "leads",
            "opportunities",
            "projects",
            "inspections",
            "estimates",
            "invoices",
            "payments",
            "calendar_events",
        ]
        module_access = {
            name: user_can_module_action(self.request.user, name, PERMISSION_VIEW)
            for name in modules
        }
        module_create = {
            name: user_can_module_action(self.request.user, name, PERMISSION_CREATE)
            for name in modules
        }

        users_queryset = UserAccount.objects.filter(id_company=company) if module_access["users"] else UserAccount.objects.none()
        employees_queryset = Employee.objects.filter(id_company=company) if module_access["employees"] else Employee.objects.none()
        clients_queryset = Client.objects.filter(id_company=company) if module_access["clients"] else Client.objects.none()
        opportunities_queryset = Lead.objects.filter(id_company=company) if module_access["opportunities"] else Lead.objects.none()
        projects_queryset = Project.objects.filter(id_company=company) if module_access["projects"] else Project.objects.none()
        estimates_queryset = Estimate.objects.filter(id_company=company) if module_access["estimates"] else Estimate.objects.none()
        invoices_queryset = Invoice.objects.filter(id_company=company) if module_access["invoices"] else Invoice.objects.none()

        legacy_inspections_queryset = (
            Inspection.objects.filter(id_project__id_company=company)
            if module_access["inspections"]
            else Inspection.objects.none()
        )
        inspection_assignments_queryset = (
            InspectionAssignment.objects.filter(client__id_company=company)
            if module_access["inspections"]
            else InspectionAssignment.objects.none()
        )
        calendar_queryset = (
            CalendarEvent.objects.filter(id_company=company)
            if module_access["calendar_events"]
            else CalendarEvent.objects.none()
        )

        active_projects_queryset = projects_queryset.exclude(status__in=["completed", "cancelled"])
        open_invoices_queryset = invoices_queryset.exclude(status=INVOICE_STATUS_VOID).exclude(
            payment_status=INVOICE_PAYMENT_STATUS_PAID
        )
        overdue_invoices_queryset = open_invoices_queryset.filter(
            due_date__lt=today,
            balance_due__gt=0,
        )
        expiring_estimates_queryset = estimates_queryset.filter(
            expiration_date__gte=today,
            expiration_date__lte=today + timedelta(days=7),
        ).exclude(status__in=["approved", "converted", "cancelled", "rejected"])
        pending_inspections_count = (
            legacy_inspections_queryset.filter(status__in=["pending", "in_progress"]).count()
            + inspection_assignments_queryset.filter(status__in=["pending", "in_progress"]).count()
        )

        recent_projects = order_queryset_safe(projects_queryset, ["-created_at", "-start_date", "-id_project"])[:5]
        recent_opportunities = order_queryset_safe(opportunities_queryset, ["-created_at", "-id_lead"])[:5]
        recent_estimates = order_queryset_safe(estimates_queryset, ["-issue_date", "-id_estimate"])[:5]
        recent_invoices = order_queryset_safe(invoices_queryset, ["-issue_date", "-id_invoice"])[:5]

        all_upcoming_calendar_items = []
        if module_access["calendar_events"]:
            all_upcoming_calendar_items = get_company_calendar_items(
                user=self.request.user,
                company=company,
                start_date=today,
                end_date=today + timedelta(days=30),
            )

        upcoming_calendar_count = len(all_upcoming_calendar_items)
        upcoming_calendar_items = all_upcoming_calendar_items[:6]
        open_invoices_count = open_invoices_queryset.count()
        overdue_invoices_count = overdue_invoices_queryset.count()
        expiring_estimates_count = expiring_estimates_queryset.count()
        attention_total = (
            overdue_invoices_count
            + expiring_estimates_count
            + pending_inspections_count
        )

        context.update(
            {
                "page_title": "Company Dashboard",
                "company": company,
                "dashboard_scope_label": company.name,
                "workspace_url": f"/{company.slug}/dashboard/",
                "today": today,
                "total_users": users_queryset.count(),
                "total_employees": employees_queryset.count(),
                "total_clients": clients_queryset.count(),
                "total_leads": opportunities_queryset.count(),
                "total_opportunities": opportunities_queryset.count(),
                "total_projects": projects_queryset.count(),
                "active_projects": active_projects_queryset.count(),
                "total_inspections": legacy_inspections_queryset.count() + inspection_assignments_queryset.count(),
                "total_estimates": estimates_queryset.count(),
                "total_invoices": invoices_queryset.count(),
                "open_invoices": open_invoices_count,
                "overdue_invoices": overdue_invoices_count,
                "expiring_estimates": expiring_estimates_count,
                "pending_inspections": pending_inspections_count,
                "attention_total": attention_total,
                "total_payments": self.get_total_payments_for_company(company) if module_access["payments"] else Decimal("0.00"),
                "total_calendar_events": calendar_queryset.count(),
                "upcoming_calendar_items": upcoming_calendar_items,
                "upcoming_calendar_count": upcoming_calendar_count,
                "recent_projects": recent_projects,
                "recent_leads": recent_opportunities,
                "recent_opportunities": recent_opportunities,
                "recent_estimates": recent_estimates,
                "recent_invoices": recent_invoices,
            }
        )

        for module_name, has_access in module_access.items():
            context[f"can_view_{module_name}"] = has_access
        for module_name, can_create in module_create.items():
            context[f"can_create_{module_name}"] = can_create

        return context
