STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"

STATUS_CHOICES = [
    (STATUS_ACTIVE, "Active"),
    (STATUS_INACTIVE, "Inactive"),
]

LANGUAGE_ENGLISH = "en"
LANGUAGE_SPANISH = "es"

LANGUAGE_CHOICES = [
    (LANGUAGE_ENGLISH, "English"),
    (LANGUAGE_SPANISH, "Español"),
]

# Company CRM modules
MODULE_DASHBOARD = "dashboard"
MODULE_COMPANIES = "companies"
MODULE_COMPANY_MODULES = "company_modules"
MODULE_ROLES = "roles"
MODULE_USERS = "users"
MODULE_EMPLOYEES = "employees"
MODULE_NOTIFICATIONS = "notifications"
MODULE_SYSTEM_LOGS = "system_logs"
MODULE_CLIENTS = "clients"
MODULE_LEADS = "leads"
MODULE_OPPORTUNITIES = "opportunities"
MODULE_PROJECTS = "projects"
MODULE_INSPECTIONS = "inspections"
MODULE_ESTIMATES = "estimates"
MODULE_INVOICES = "invoices"
MODULE_PAYMENTS = "payments"
MODULE_SUPPLIERS = "suppliers"
MODULE_INTEGRATIONS = "integrations"
MODULE_CONTRACTS = "contracts"
MODULE_EVIDENCE = "evidence"
MODULE_SUPERVISION = "supervision"
MODULE_CALENDAR = "calendar_events"
MODULE_CALENDAR_EVENTS = "calendar_events"
MODULE_REPORTS = "reports"
MODULE_SMTP_SETTINGS = "smtp_settings"

# Platform / CEO MARKETING SaaS admin modules
PLATFORM_DASHBOARD = "platform_dashboard"
PLATFORM_COMPANIES = "platform_companies"
PLATFORM_PLANS = "platform_plans"
PLATFORM_SUBSCRIPTIONS = "platform_subscriptions"
PLATFORM_DOCUMENTS = "platform_documents"
PLATFORM_PAYMENTS = "platform_payments"
PLATFORM_CALENDAR = "platform_calendar"
PLATFORM_EMAIL = "platform_email"
PLATFORM_NOTIFICATIONS = "platform_notifications"
PLATFORM_AUDIT = "platform_audit"
PLATFORM_METRICS = "platform_metrics"
PLATFORM_SYSTEM_MONITOR = "platform_system_monitor"

MODULE_CHOICES = [
    (MODULE_DASHBOARD, "Dashboard"),
    (MODULE_COMPANIES, "Companies"),
    (MODULE_COMPANY_MODULES, "Company Modules"),
    (MODULE_ROLES, "Roles"),
    (MODULE_USERS, "Users"),
    (MODULE_EMPLOYEES, "Employees"),
    (MODULE_NOTIFICATIONS, "Notifications"),
    (MODULE_SYSTEM_LOGS, "History"),
    (MODULE_CLIENTS, "Clients"),
    (MODULE_LEADS, "Leads"),
    (MODULE_OPPORTUNITIES, "Opportunities"),
    (MODULE_PROJECTS, "Projects"),
    (MODULE_INSPECTIONS, "Inspections"),
    (MODULE_ESTIMATES, "Estimates"),
    (MODULE_INVOICES, "Invoices"),
    (MODULE_PAYMENTS, "Payments"),
    (MODULE_SUPPLIERS, "Suppliers"),
    (MODULE_INTEGRATIONS, "Integrations"),
    (MODULE_CONTRACTS, "Contracts"),
    (MODULE_EVIDENCE, "Evidence"),
    (MODULE_SUPERVISION, "Supervision"),
    (MODULE_CALENDAR_EVENTS, "Calendar Events"),
    (MODULE_REPORTS, "Reports"),
    (MODULE_SMTP_SETTINGS, "SMTP Settings"),

    (PLATFORM_DASHBOARD, "Platform Dashboard"),
    (PLATFORM_COMPANIES, "Platform Companies"),
    (PLATFORM_PLANS, "Platform Plans"),
    (PLATFORM_SUBSCRIPTIONS, "Platform Subscriptions"),
    (PLATFORM_DOCUMENTS, "Platform Documents"),
    (PLATFORM_PAYMENTS, "Platform Payments"),
    (PLATFORM_CALENDAR, "Platform Calendar"),
    (PLATFORM_EMAIL, "Platform Email"),
    (PLATFORM_NOTIFICATIONS, "Platform Notifications"),
    (PLATFORM_AUDIT, "Platform Audit"),
    (PLATFORM_METRICS, "Platform Metrics"),
    (PLATFORM_SYSTEM_MONITOR, "Platform System Monitor"),
]


# Only modules that belong to a company workspace. Global company management
# and every platform_* module are intentionally excluded from tenant roles.
TENANT_EXCLUDED_MODULE_CODES = {
    MODULE_COMPANIES,
    MODULE_COMPANY_MODULES,
    # Employees and users now share one workspace module. The legacy code is
    # retained only so old URLs/data can be migrated without breaking imports.
    MODULE_EMPLOYEES,
}

TENANT_MODULE_CHOICES = [
    (code, label)
    for code, label in MODULE_CHOICES
    if not code.startswith("platform_") and code not in TENANT_EXCLUDED_MODULE_CODES
]

TENANT_MODULE_CODES = [code for code, _label in TENANT_MODULE_CHOICES]
