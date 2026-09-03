from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse

from apps.core.context_processors import company_scoped_url


class CompanyNavigationRouteTests(SimpleTestCase):
    # Keep this list aligned with the routes that are actually rendered by
    # apps.core.context_processors.crm_context for a company workspace.
    ROUTES = (
        "dashboard:dashboard_home",
        "clients:client_list",
        "opportunities:opportunity_list",
        "calendar_events:calendar_event_list",
        "projects:project_list",
        "inspections:inspection_list",
        "estimates:estimate_list",
        "contracts:contract_list",
        "invoices:invoice_list",
        "payments:payment_list",
        "payments:finance_clients",
        "reports:reports_home",
        "suppliers:supplier_list",
        "suppliers:offer_list",
        "suppliers:purchase_list",
        "suppliers:reports",
        "accounts:user_account_list",
        "accounts:role_list",
        "smtp_settings:form",
        "languages:settings",
        "notifications:notification_list",
        "integrations:dashboard",
        "integrations:calendar_list",
        "integrations:drive_list",
        "integrations:analytics_report",
        "integrations:logs",
    )

    def test_every_company_menu_route_reverses(self):
        for route_name in self.ROUTES:
            with self.subTest(route_name=route_name):
                self.assertNotEqual(reverse(route_name), "#")

    def test_company_scoped_url_preserves_workspace_slug(self):
        company = SimpleNamespace(slug="peluche-roofing")
        self.assertEqual(
            company_scoped_url(company, route_name="estimates:estimate_list"),
            "/peluche-roofing/estimates/",
        )
        self.assertEqual(
            company_scoped_url(company, route_name="payments:finance_clients"),
            "/peluche-roofing/payments/finance/clients/",
        )


class CompanyNavigationActiveTrackerTests(SimpleTestCase):
    def test_route_specific_items_do_not_activate_together(self):
        from apps.core.context_processors import build_nav_item, mark_item_active

        payments = build_nav_item(
            "Payments",
            "/acme/payments/",
            "payments",
            active_view_prefixes=("payment_",),
        )
        summary = build_nav_item(
            "Client Financial Summary",
            "/acme/payments/finance/clients/",
            "payments",
            active_view_prefixes=("finance_",),
        )

        mark_item_active(
            payments,
            "company_payments",
            current_url_name="finance_clients",
            request_path="/acme/payments/finance/clients/",
        )
        mark_item_active(
            summary,
            "company_payments",
            current_url_name="finance_clients",
            request_path="/acme/payments/finance/clients/",
        )

        self.assertFalse(payments["is_active"])
        self.assertTrue(summary["is_active"])

    def test_payment_detail_keeps_only_payments_active(self):
        from apps.core.context_processors import build_nav_item, mark_item_active

        payments = build_nav_item(
            "Payments",
            "/acme/payments/",
            "payments",
            active_view_prefixes=("payment_",),
        )
        summary = build_nav_item(
            "Client Financial Summary",
            "/acme/payments/finance/clients/",
            "payments",
            active_view_prefixes=("finance_",),
        )

        mark_item_active(
            payments,
            "company_payments",
            current_url_name="payment_detail",
            request_path="/acme/payments/42/",
        )
        mark_item_active(
            summary,
            "company_payments",
            current_url_name="payment_detail",
            request_path="/acme/payments/42/",
        )

        self.assertTrue(payments["is_active"])
        self.assertFalse(summary["is_active"])
