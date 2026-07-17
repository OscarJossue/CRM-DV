from decimal import Decimal

from apps.clients.models import Client
from apps.estimates.models import Estimate
from apps.invoices.models import Invoice
from apps.leads.models import Lead
from apps.payments.models import Payment
from apps.projects.models import Project


VALID_PAID_STATUSES = [
    "paid",
    "verified",
    "completed",
]


def get_company_for_user(user):
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return None

    return user.id_company


def filter_by_company(queryset, company_field, company):
    if company:
        return queryset.filter(**{company_field: company})

    return queryset


def get_report_querysets(user):
    company = get_company_for_user(user)

    clients = filter_by_company(Client.objects.all(), "id_company", company)
    leads = filter_by_company(Lead.objects.all(), "id_company", company)
    projects = filter_by_company(Project.objects.all(), "id_company", company)
    estimates = filter_by_company(Estimate.objects.all(), "id_company", company)
    invoices = filter_by_company(Invoice.objects.all(), "id_company", company)

    invoice_ids = invoices.values_list("id_invoice", flat=True)

    payments = Payment.objects.select_related(
        "id_invoice",
        "id_invoice__id_company",
        "id_invoice__id_client",
        "id_project",
    ).filter(
        id_invoice_id__in=invoice_ids,
    )

    return {
        "company": company,
        "clients": clients,
        "leads": leads,
        "projects": projects,
        "estimates": estimates,
        "invoices": invoices,
        "payments": payments,
    }


def decimal_sum(queryset, field_name):
    total = Decimal("0.00")

    for value in queryset.values_list(field_name, flat=True):
        total += value or Decimal("0.00")

    return total


def get_financial_summary(user):
    querysets = get_report_querysets(user)

    invoices = querysets["invoices"]
    payments = querysets["payments"]
    projects = querysets["projects"]
    estimates = querysets["estimates"]

    paid_payments = payments.filter(status__in=VALID_PAID_STATUSES)

    active_projects = projects.exclude(
        status__in=[
            "completed",
            "cancelled",
        ]
    )

    summary = {
        "company": querysets["company"],
        "total_clients": querysets["clients"].count(),
        "total_leads": querysets["leads"].count(),
        "total_projects": projects.count(),
        "active_projects": active_projects.count(),
        "total_estimates": estimates.count(),
        "total_estimated": decimal_sum(estimates, "total"),
        "total_invoices": invoices.count(),
        "total_billed": decimal_sum(invoices, "total"),
        "total_balance": decimal_sum(invoices, "balance"),
        "total_payments": paid_payments.count(),
        "total_paid": decimal_sum(paid_payments, "amount"),
        "pending_payments": payments.filter(status="pending_payment").count(),
        "verified_payments": payments.filter(status="verified").count(),
    }

    return summary


def get_project_summary(user):
    querysets = get_report_querysets(user)
    projects = querysets["projects"]

    return {
        "total_projects": projects.count(),
        "pending_projects": projects.filter(status="pending").count(),
        "active_projects": projects.exclude(status__in=["completed", "cancelled"]).count(),
        "completed_projects": projects.filter(status="completed").count(),
        "cancelled_projects": projects.filter(status="cancelled").count(),
    }


def get_payment_summary(user):
    querysets = get_report_querysets(user)
    payments = querysets["payments"]

    paid_payments = payments.filter(status__in=VALID_PAID_STATUSES)

    return {
        "total_payments": payments.count(),
        "pending_payments": payments.filter(status="pending_payment").count(),
        "paid_payments": payments.filter(status="paid").count(),
        "verified_payments": payments.filter(status="verified").count(),
        "rejected_payments": payments.filter(status="rejected").count(),
        "cancelled_payments": payments.filter(status="cancelled").count(),
        "total_paid": decimal_sum(paid_payments, "amount"),
    }
