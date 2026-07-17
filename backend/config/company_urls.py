from django.urls import include, path


def company_include(urlconf_path, namespace):
    return include((urlconf_path, namespace), namespace=namespace)


urlpatterns = [
    # Accounts from develoverps already include:
    # users/, roles/, permissions/, login/, logout/
    # So we mount it at company root, not under /users/.
    path("", company_include("apps.accounts.urls", "company_accounts")),

    path("dashboard/", company_include("apps.dashboard.urls", "company_dashboard")),
    path("field-work/", company_include("apps.contractor_portal.urls", "company_contractor_portal")),
    path("employees/", company_include("apps.employees.urls", "company_employees")),

    path("clients/", company_include("apps.clients.urls", "company_clients")),
    path("leads/", company_include("apps.leads.urls", "company_leads")),
    path("opportunities/", company_include("apps.opportunities.urls", "company_opportunities")),
    path("projects/", company_include("apps.projects.urls", "company_projects")),
    path("inspections/", company_include("apps.inspections.urls", "company_inspections")),
    path("user-activities/", company_include("apps.user_activities.urls", "company_user_activities")),
    path("system-logs/", company_include("apps.audit.urls", "company_audit")),
    path("evidence/", company_include("apps.evidence.urls", "company_evidence")),

    path("calendar/", company_include("apps.calendar_events.urls", "company_calendar")),
    path("calendar-events/", company_include("apps.calendar_events.urls", "company_calendar_alt")),

    path("estimates/", company_include("apps.estimates.urls", "company_estimates")),
    path("invoices/", company_include("apps.invoices.urls", "company_invoices")),
    path("payments/", company_include("apps.payments.urls", "company_payments")),
    path("suppliers/", company_include("apps.suppliers.urls", "company_suppliers")),
    path("integrations/", company_include("apps.integrations.urls", "company_integrations")),
    path("contracts/", company_include("apps.contracts.urls", "company_contracts")),
    path("reports/", company_include("apps.reports.urls", "company_reports")),
    path("smtp-settings/", company_include("apps.smtp_settings.urls", "company_smtp_settings")),
    path("languages/", company_include("apps.languages.urls", "company_languages")),
    path("notifications/", company_include("apps.notifications.urls", "company_notifications")),
]