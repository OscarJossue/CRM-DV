from decimal import Decimal

from django.apps import apps
from django.db.models import Count, Sum


def get_model_safe(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def queryset_safe(app_label, model_name):
    model = get_model_safe(app_label, model_name)

    if not model:
        return None

    try:
        return model.objects.all()
    except Exception:
        return None


def filter_company_safe(queryset, company, filter_path="id_company"):
    if queryset is None:
        return None

    if not company:
        return queryset

    try:
        return queryset.filter(**{filter_path: company})
    except Exception:
        return queryset.none()


def count_safe(queryset):
    if queryset is None:
        return 0

    try:
        return queryset.count()
    except Exception:
        return 0


def sum_safe(queryset, field_name):
    if queryset is None:
        return Decimal("0.00")

    try:
        value = queryset.aggregate(total=Sum(field_name)).get("total")
        return value or Decimal("0.00")
    except Exception:
        return Decimal("0.00")


def status_counts_safe(queryset, status_field="status"):
    if queryset is None:
        return []

    try:
        rows = queryset.values(status_field).annotate(total=Count(status_field)).order_by(status_field)

        return [
            {
                "label": row.get(status_field) or "unknown",
                "value": row.get("total") or 0,
            }
            for row in rows
        ]
    except Exception:
        return []


def get_company_for_user(user):
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return None

    return getattr(user, "id_company", None)

def get_company_by_id_safe(company_id):
    if not company_id:
        return None

    try:
        Company = apps.get_model("companies", "Company")
        return Company.objects.filter(id_company=company_id).first()
    except Exception:
        return None


def get_dashboard_resource_metrics(user, company_id=None):
    user_is_superuser = bool(user and user.is_authenticated and user.is_superuser)
    selected_company = get_company_by_id_safe(company_id) if user_is_superuser else None

    is_global = bool(user_is_superuser and not selected_company)

    if user_is_superuser and selected_company:
        company = selected_company
    else:
        company = get_company_for_user(user)

    companies_qs = queryset_safe("companies", "Company")
    users_qs = queryset_safe("accounts", "UserAccount")
    company_modules_qs = queryset_safe("company_modules", "CompanyModule")

    employees_qs = filter_company_safe(
        queryset_safe("employees", "Employee"),
        company,
        "id_company",
    )
    clients_qs = filter_company_safe(
        queryset_safe("clients", "Client"),
        company,
        "id_company",
    )
    leads_qs = filter_company_safe(
        queryset_safe("leads", "Lead"),
        company,
        "id_company",
    )
    projects_qs = filter_company_safe(
        queryset_safe("projects", "Project"),
        company,
        "id_company",
    )
    inspections_qs = filter_company_safe(
        queryset_safe("inspections", "Inspection"),
        company,
        "id_project__id_company",
    )
    evidence_qs = filter_company_safe(
        queryset_safe("evidence", "EvidenceFile"),
        company,
        "id_project__id_company",
    )
    supervisions_qs = filter_company_safe(
        queryset_safe("supervision", "Supervision"),
        company,
        "id_project__id_company",
    )
    calendar_qs = filter_company_safe(
        queryset_safe("calendar_events", "CalendarEvent"),
        company,
        "id_company",
    )
    estimates_qs = filter_company_safe(
        queryset_safe("estimates", "Estimate"),
        company,
        "id_company",
    )
    invoices_qs = filter_company_safe(
        queryset_safe("invoices", "Invoice"),
        company,
        "id_company",
    )
    payments_qs = filter_company_safe(
        queryset_safe("payments", "Payment"),
        company,
        "id_invoice__id_company",
    )
    contracts_qs = filter_company_safe(
        queryset_safe("contracts", "Contract"),
        company,
        "id_project__id_company",
    )
    logs_qs = filter_company_safe(
        queryset_safe("audit", "SystemLog"),
        company,
        "id_company",
    )

    if is_global:
        users_scope_qs = users_qs
        modules_scope_qs = company_modules_qs
    else:
        users_scope_qs = filter_company_safe(users_qs, company, "id_company")
        modules_scope_qs = filter_company_safe(company_modules_qs, company, "id_company")

    active_projects = 0
    if projects_qs is not None:
        try:
            active_projects = projects_qs.exclude(status__in=["completed", "cancelled"]).count()
        except Exception:
            active_projects = 0

    enabled_modules = 0
    if modules_scope_qs is not None:
        try:
            enabled_modules = modules_scope_qs.filter(is_enabled=True).count()
        except Exception:
            enabled_modules = 0

    total_billed = sum_safe(invoices_qs, "total")
    total_balance = sum_safe(invoices_qs, "balance")
    total_paid = sum_safe(payments_qs.filter(status="completed") if payments_qs is not None else None, "amount")

    cards = [
        {"label": "Companies", "value": count_safe(companies_qs) if is_global else 1},
        {"label": "Users", "value": count_safe(users_scope_qs)},
        {"label": "Enabled Modules", "value": enabled_modules},
        {"label": "Employees", "value": count_safe(employees_qs)},
        {"label": "Clients", "value": count_safe(clients_qs)},
        {"label": "Leads", "value": count_safe(leads_qs)},
        {"label": "Projects", "value": count_safe(projects_qs)},
        {"label": "Active Projects", "value": active_projects},
        {"label": "Estimates", "value": count_safe(estimates_qs)},
        {"label": "Invoices", "value": count_safe(invoices_qs)},
        {"label": "Payments", "value": count_safe(payments_qs)},
        {"label": "Contracts", "value": count_safe(contracts_qs)},
    ]

    operational_chart = {
        "labels": [
            "Employees",
            "Clients",
            "Leads",
            "Projects",
            "Inspections",
            "Evidence",
            "Supervision",
            "Calendar",
        ],
        "values": [
            count_safe(employees_qs),
            count_safe(clients_qs),
            count_safe(leads_qs),
            count_safe(projects_qs),
            count_safe(inspections_qs),
            count_safe(evidence_qs),
            count_safe(supervisions_qs),
            count_safe(calendar_qs),
        ],
    }

    financial_chart = {
        "labels": ["Billed", "Paid", "Balance"],
        "values": [
            float(total_billed),
            float(total_paid),
            float(total_balance),
        ],
    }

    project_status_chart = status_counts_safe(projects_qs)

    company_plan_chart = []
    if is_global and companies_qs is not None:
        try:
            rows = companies_qs.values("plan").annotate(total=Count("plan")).order_by("plan")
            company_plan_chart = [
                {
                    "label": row.get("plan") or "unknown",
                    "value": row.get("total") or 0,
                }
                for row in rows
            ]
        except Exception:
            company_plan_chart = []

    return {
        "is_global": is_global,
        "company_name": company.name if company else "SaaS Global",
        "selected_company_id": company.id_company if company else None,
        "cards": cards,
        "financial": {
            "total_billed": float(total_billed),
            "total_paid": float(total_paid),
            "total_balance": float(total_balance),
        },
        "charts": {
            "operational": operational_chart,
            "financial": financial_chart,
            "project_status": project_status_chart,
            "company_plans": company_plan_chart,
        },
    }