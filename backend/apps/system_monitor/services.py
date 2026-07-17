import time

from django.apps import apps
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.urls import NoReverseMatch, reverse


MODULE_LABELS = {
    "companies": "Companies",
    "users": "Users",
    "roles": "Roles",
    "employees": "Employees",
    "notifications": "Notifications",
    "clients": "Clients",
    "leads": "Leads",
    "projects": "Projects",
    "inspections": "Inspections",
    "evidence_files": "Evidence Files",
    "supervisions": "Supervisions",
    "calendar_events": "Calendar Events",
    "estimates": "Estimates",
    "invoices": "Invoices",
    "payments": "Payments",
    "contracts": "Contracts",
    "reports": "Reports",
    "system_logs": "History",
    "company_modules": "Company Modules",
}


def get_model_count(app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
        return model.objects.count()
    except Exception:
        return 0


def count_model_filtered(app_label, model_name, **filters):
    try:
        model = apps.get_model(app_label, model_name)
        queryset = model.objects.all()

        if filters:
            queryset = queryset.filter(**filters)

        return queryset.count()
    except Exception:
        return 0


def get_company_by_id_safe(company_id):
    if not company_id:
        return None

    try:
        Company = apps.get_model("companies", "Company")
        return Company.objects.filter(id_company=company_id).first()
    except Exception:
        return None


def check_url_name(url_name):
    try:
        url = reverse(url_name)

        return {
            "name": url_name,
            "url": url,
            "available": True,
        }
    except NoReverseMatch:
        return {
            "name": url_name,
            "url": None,
            "available": False,
        }


def get_database_status():
    started_at = time.perf_counter()

    try:
        connection.ensure_connection()

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        response_ms = round((time.perf_counter() - started_at) * 1000, 2)

        try:
            table_names = connection.introspection.table_names()
        except Exception:
            table_names = []

        return {
            "connected": True,
            "engine": connection.vendor,
            "database_name": str(connection.settings_dict.get("NAME") or ""),
            "table_count": len(table_names),
            "response_ms": response_ms,
            "error": None,
        }

    except Exception as error:
        response_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return {
            "connected": False,
            "engine": connection.vendor if connection else "unknown",
            "database_name": None,
            "table_count": 0,
            "response_ms": response_ms,
            "error": str(error),
        }


def get_migration_status():
    try:
        applied_count = MigrationRecorder.Migration.objects.count()

        return {
            "available": True,
            "applied_count": applied_count,
            "error": None,
        }
    except Exception as error:
        return {
            "available": False,
            "applied_count": 0,
            "error": str(error),
        }


def get_company_for_user(user):
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return None

    return getattr(user, "id_company", None)


def company_has_module_enabled(company, module_name):
    if not company:
        return False

    try:
        CompanyModule = apps.get_model("company_modules", "CompanyModule")

        return CompanyModule.objects.filter(
            id_company=company,
            module=module_name,
            is_enabled=True,
        ).exists()
    except Exception:
        return True


def user_can_view_module(user, module_name, scoped_company=None):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        if scoped_company:
            return company_has_module_enabled(scoped_company, module_name)
        return True

    company = getattr(user, "id_company", None)

    if not company:
        return False

    if scoped_company and company.id_company != scoped_company.id_company:
        return False

    if not company_has_module_enabled(company, module_name):
        return False

    role = getattr(user, "id_role", None)

    if not role:
        return False

    try:
        RolePermission = apps.get_model("accounts", "RolePermission")

        return RolePermission.objects.filter(
            id_role=role,
            module=module_name,
            can_view=True,
        ).exists()
    except Exception:
        return False


def build_metric(label, value, module=None):
    return {
        "label": label,
        "value": value,
        "module": module,
    }


def get_company_workspace_sections(user, company):
    sections = []

    if not company:
        return sections

    overview_cards = [
        build_metric("Company", company.name),
        build_metric("Plan", company.get_plan_display()),
        build_metric("Status", company.get_status_display()),
        build_metric("User Limit", company.user_limit),
    ]

    sections.append(
        {
            "title": "Workspace Overview",
            "description": "General company workspace status and assigned SaaS plan.",
            "cards": overview_cards,
        }
    )

    access_cards = []

    if user_can_view_module(user, "users", company):
        access_cards.append(
            build_metric(
                "Users",
                count_model_filtered("accounts", "UserAccount", id_company=company),
                "users",
            )
        )
        access_cards.append(
            build_metric(
                "Active Users",
                count_model_filtered(
                    "accounts",
                    "UserAccount",
                    id_company=company,
                    status="active",
                    is_active=True,
                ),
                "users",
            )
        )

    if user_can_view_module(user, "roles", company):
        access_cards.append(
            build_metric(
                "Roles",
                count_model_filtered("accounts", "Role", id_company=company),
                "roles",
            )
        )

    if user_can_view_module(user, "company_modules", company):
        access_cards.append(
            build_metric(
                "Enabled Modules",
                count_model_filtered(
                    "company_modules",
                    "CompanyModule",
                    id_company=company,
                    is_enabled=True,
                ),
                "company_modules",
            )
        )

    if access_cards:
        sections.append(
            {
                "title": "Access & Modules",
                "description": "Users, roles and enabled modules visible according to permissions.",
                "cards": access_cards,
            }
        )

    operations_cards = []

    operation_sources = [
        ("employees", "Employees", "employees", "Employee", {"id_company": company}),
        ("clients", "Clients", "clients", "Client", {"id_company": company}),
        ("leads", "Leads", "leads", "Lead", {"id_company": company}),
        ("projects", "Projects", "projects", "Project", {"id_company": company}),
        ("inspections", "Inspections", "inspections", "Inspection", {"id_project__id_company": company}),
        ("evidence_files", "Evidence Files", "evidence", "EvidenceFile", {"id_project__id_company": company}),
        ("supervisions", "Supervisions", "supervision", "Supervision", {"id_project__id_company": company}),
        ("calendar_events", "Calendar Events", "calendar_events", "CalendarEvent", {"id_company": company}),
    ]

    for module_name, label, app_label, model_name, filters in operation_sources:
        if user_can_view_module(user, module_name, company):
            operations_cards.append(
                build_metric(
                    label,
                    count_model_filtered(app_label, model_name, **filters),
                    module_name,
                )
            )

    if operations_cards:
        sections.append(
            {
                "title": "Operations",
                "description": "Operational records from modules the user can view.",
                "cards": operations_cards,
            }
        )

    finance_cards = []

    finance_sources = [
        ("estimates", "Estimates", "estimates", "Estimate", {"id_company": company}),
        ("invoices", "Invoices", "invoices", "Invoice", {"id_company": company}),
        ("payments", "Payments", "payments", "Payment", {"id_invoice__id_company": company}),
        ("contracts", "Contracts", "contracts", "Contract", {"id_project__id_company": company}),
    ]

    for module_name, label, app_label, model_name, filters in finance_sources:
        if user_can_view_module(user, module_name, company):
            finance_cards.append(
                build_metric(
                    label,
                    count_model_filtered(app_label, model_name, **filters),
                    module_name,
                )
            )

    if finance_cards:
        sections.append(
            {
                "title": "Finance & Documents",
                "description": "Financial and document resources available for this workspace.",
                "cards": finance_cards,
            }
        )

    activity_cards = []

    if user_can_view_module(user, "system_logs", company):
        activity_cards.append(
            build_metric(
                "History",
                count_model_filtered("audit", "SystemLog", id_company=company),
                "system_logs",
            )
        )

    if user_can_view_module(user, "notifications", company):
        activity_cards.append(
            build_metric(
                "Notifications",
                count_model_filtered(
                    "notifications",
                    "Notification",
                    id_user__id_company=company,
                ),
                "notifications",
            )
        )

    if activity_cards:
        sections.append(
            {
                "title": "System Activity",
                "description": "Activity records available according to workspace permissions.",
                "cards": activity_cards,
            }
        )

    return sections


def get_global_system_sections():
    database = get_database_status()
    migrations = get_migration_status()

    installed_apps = [
        app_config.name
        for app_config in apps.get_app_configs()
    ]

    endpoints = [
        check_url_name("health_check"),
        check_url_name("prometheus-django-metrics"),
        check_url_name("dashboard:dashboard_home"),
        check_url_name("dashboard_metrics:resources_dashboard"),
        check_url_name("system_monitor:status"),
    ]

    sections = [
        {
            "title": "SaaS Technical Health",
            "description": "Internal platform resources visible only for the global superuser.",
            "cards": [
                build_metric("Backend", "Online"),
                build_metric("Database", "Connected" if database["connected"] else "Disconnected"),
                build_metric("DB Response", f'{database["response_ms"]} ms'),
                build_metric("Tables", database["table_count"]),
                build_metric("Installed Apps", len(installed_apps)),
                build_metric("Applied Migrations", migrations["applied_count"]),
            ],
        },
        {
            "title": "SaaS Platform Counters",
            "description": "Global counters across all companies and platform access records.",
            "cards": [
                build_metric("Companies", get_model_count("companies", "Company")),
                build_metric("Users", get_model_count("accounts", "UserAccount")),
                build_metric("Roles", get_model_count("accounts", "Role")),
                build_metric("Role Permissions", get_model_count("accounts", "RolePermission")),
                build_metric("Company Modules", get_model_count("company_modules", "CompanyModule")),
                build_metric("History", get_model_count("audit", "SystemLog")),
            ],
        },
    ]

    return {
        "database": database,
        "migrations": migrations,
        "endpoints": endpoints,
        "installed_apps": installed_apps,
        "sections": sections,
    }


def get_system_monitor_data(user=None, company_id=None):
    user_is_superuser = bool(user and user.is_authenticated and user.is_superuser)
    selected_company = get_company_by_id_safe(company_id) if user_is_superuser else None

    if user_is_superuser and not selected_company:
        global_data = get_global_system_sections()

        return {
            "is_global": True,
            "scope_name": "SaaS Global",
            "database": global_data["database"],
            "migrations": global_data["migrations"],
            "endpoints": global_data["endpoints"],
            "installed_apps": global_data["installed_apps"],
            "sections": global_data["sections"],
            "selected_company_id": None,
        }

    if user_is_superuser and selected_company:
        company = selected_company
    else:
        company = get_company_for_user(user)

    return {
        "is_global": False,
        "scope_name": company.name if company else "No company assigned",
        "company_id": company.id_company if company else None,
        "database": None,
        "migrations": None,
        "endpoints": [],
        "installed_apps": [],
        "sections": get_company_workspace_sections(user, company) if company else [],
        "selected_company_id": company.id_company if company else None,
    }