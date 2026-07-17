from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.invoices.views import build_invoice_action_urls, reverse_invoice_url


class InvoiceRouteIntegrityTests(SimpleTestCase):
    route_cases = [
        ("invoice_list", {}),
        ("invoice_create", {}),
        ("invoice_create_for_project", {"id_project": 7}),
        ("invoice_detail", {"id_invoice": 8}),
        ("invoice_update", {"id_invoice": 8}),
        ("invoice_generate", {"id_invoice": 8}),
        ("invoice_send", {"id_invoice": 8}),
        ("invoice_mark_sent", {"id_invoice": 8}),
        ("invoice_void", {"id_invoice": 8}),
        ("invoice_pdf_style", {"id_invoice": 8}),
        ("invoice_pdf", {"id_invoice": 8}),
    ]

    def build_request(self, url):
        request = RequestFactory().get(url)
        request.resolver_match = resolve(url)
        return request

    def test_all_legacy_invoice_routes_resolve(self):
        for name, kwargs in self.route_cases:
            with self.subTest(name=name):
                url = reverse(f"invoices:{name}", kwargs=kwargs)
                match = resolve(url)
                self.assertEqual(match.url_name, name)
                self.assertEqual(match.namespace, "invoices")

    def test_all_company_invoice_routes_resolve(self):
        for name, kwargs in self.route_cases:
            with self.subTest(name=name):
                company_kwargs = {"company_slug": "peluche-roofing", **kwargs}
                url = reverse(f"company_invoices:{name}", kwargs=company_kwargs)
                match = resolve(url)
                self.assertEqual(match.url_name, name)
                self.assertEqual(match.namespace, "company_invoices")
                self.assertTrue(url.startswith("/peluche-roofing/invoices/"))

    def test_action_urls_keep_company_prefix(self):
        request = self.build_request("/peluche-roofing/invoices/8/")
        invoice = SimpleNamespace(id_invoice=8, id_project_id=7)
        urls = build_invoice_action_urls(request, invoice)

        for key in ["list", "create", "detail", "edit", "generate", "send", "mark_sent", "void", "pdf_style", "pdf"]:
            with self.subTest(key=key):
                self.assertTrue(urls[key].startswith("/peluche-roofing/invoices/"))
                resolve(urls[key])

        self.assertTrue(urls["payment_create"].startswith("/peluche-roofing/payments/"))
        self.assertTrue(urls["project_detail"].startswith("/peluche-roofing/projects/"))
        resolve(urls["payment_create"])
        resolve(urls["project_detail"])

    def test_action_urls_keep_legacy_prefix(self):
        request = self.build_request("/invoices/8/")
        invoice = SimpleNamespace(id_invoice=8, id_project_id=7)
        urls = build_invoice_action_urls(request, invoice)

        self.assertEqual(urls["detail"], "/invoices/8/")
        self.assertEqual(urls["edit"], "/invoices/8/edit/")
        self.assertEqual(urls["payment_create"], "/payments/invoices/8/create/")
        self.assertEqual(urls["project_detail"], "/projects/7/")

    def test_reverse_helper_matches_current_namespace(self):
        company_request = self.build_request("/peluche-roofing/invoices/")
        legacy_request = self.build_request("/invoices/")

        self.assertEqual(
            reverse_invoice_url(company_request, "invoice_detail", kwargs={"id_invoice": 8}),
            "/peluche-roofing/invoices/8/",
        )
        self.assertEqual(
            reverse_invoice_url(legacy_request, "invoice_detail", kwargs={"id_invoice": 8}),
            "/invoices/8/",
        )
