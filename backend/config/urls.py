from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.accounts.views import CRMLoginView, CRMLogoutView
from apps.languages.views import PublicLanguageSwitchView


def health_check(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "crm_saas_backend",
        }
    )


def legacy_include(urlconf_path, namespace):
    return include((urlconf_path, namespace), namespace=namespace)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),

    path("", include("django_prometheus.urls")),

    path("login/", CRMLoginView.as_view(), name="login"),
    path("logout/", CRMLogoutView.as_view(), name="logout"),
    path(
        "language/select/",
        PublicLanguageSwitchView.as_view(),
        name="language_switch",
    ),

    # Platform SaaS admin
    path("", include("apps.platform_core.urls")),
    path("crm/companies/", include("apps.companies.urls")),
    path("crm/plans/", include("apps.platform_plans.urls")),
    path("crm/subscriptions/", include("apps.platform_subscriptions.urls")),
    path("crm/platform-email/", include("apps.platform_email.urls")),
    path("crm/documents/", include("apps.platform_documents.urls")),
    path("crm/payments/", include("apps.platform_payments.urls")),
    path("crm/calendar/", include("apps.platform_calendar.urls")),
    path("crm/notifications/", include("apps.platform_notifications.urls")),
    path("crm/audit/", include("apps.platform_audit.urls")),
    path("crm/platform-users/", include("apps.platform_users.urls")),
    path("crm/language/", include("apps.languages.platform_urls")),

    path("dashboard-metrics/", include("apps.dashboard_metrics.urls")),
    path("system-monitor/", include("apps.system_monitor.urls")),

    # Auth and platform APIs. The company router is mounted at /api/companies/;
    # the legacy nested route remains temporarily for backwards compatibility.
    path("api/", include("apps.accounts.api_urls")),
    path("api/", include("apps.companies.api_urls")),
    path("api/companies/", include("apps.companies.api_urls")),

    # Legacy namespaces for company CRM templates from develoverps.
    path("dashboard/", legacy_include("apps.dashboard.urls", "dashboard")),
    path("", legacy_include("apps.accounts.urls", "accounts")),
    path("employees/", legacy_include("apps.employees.urls", "employees")),

    path("clients/", legacy_include("apps.clients.urls", "clients")),
    path("leads/", legacy_include("apps.leads.urls", "leads")),
    path("opportunities/", legacy_include("apps.opportunities.urls", "opportunities")),
    path("projects/", legacy_include("apps.projects.urls", "projects")),
    path("inspections/", legacy_include("apps.inspections.urls", "inspections")),
    path("user-activities/", legacy_include("apps.user_activities.urls", "user_activities")),
    path("evidence/", legacy_include("apps.evidence.urls", "evidence")),

    path("calendar-events/", legacy_include("apps.calendar_events.urls", "calendar_events")),
    path("estimates/", legacy_include("apps.estimates.urls", "estimates")),
    path("invoices/", legacy_include("apps.invoices.urls", "invoices")),
    path("payments/", legacy_include("apps.payments.urls", "payments")),
    path("suppliers/", legacy_include("apps.suppliers.urls", "suppliers")),
    path("integrations/", legacy_include("apps.integrations.urls", "integrations")),
    path("contracts/", legacy_include("apps.contracts.urls", "contracts")),
    path("reports/", legacy_include("apps.reports.urls", "reports")),
    path("smtp-settings/", legacy_include("apps.smtp_settings.urls", "smtp_settings")),
    path("languages/", legacy_include("apps.languages.urls", "languages")),
    path("notifications/", legacy_include("apps.notifications.urls", "notifications")),

    path("company-modules/", legacy_include("apps.company_modules.urls", "company_modules")),
    path("system-logs/", legacy_include("apps.audit.urls", "audit")),

    # Company CRM routes. Keep this at the end.
    path("<slug:company_slug>/", include("config.company_urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler403 = "apps.core.views.permission_denied_view"
handler404 = "django.views.defaults.page_not_found"