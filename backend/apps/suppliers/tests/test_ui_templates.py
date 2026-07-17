from pathlib import Path

from django.template.loader import get_template
from django.test import SimpleTestCase


class SupplierUnifiedUITemplateTests(SimpleTestCase):
    template_names = [
        "suppliers/supplier_list.html",
        "suppliers/supplier_form.html",
        "suppliers/supplier_detail.html",
        "suppliers/offer_list.html",
        "suppliers/offer_form.html",
        "suppliers/purchase_list.html",
        "suppliers/purchase_form.html",
        "suppliers/purchase_detail.html",
        "suppliers/reports.html",
        "suppliers/document_form.html",
    ]

    def test_all_supplier_templates_compile(self):
        for name in self.template_names:
            with self.subTest(name=name):
                self.assertIsNotNone(get_template(name))

    def test_internal_create_and_detail_templates_use_invoice_standard(self):
        base = Path(__file__).resolve().parents[1] / "templates" / "suppliers"
        for name in [
            "supplier_form.html",
            "supplier_detail.html",
            "offer_form.html",
            "purchase_form.html",
            "purchase_detail.html",
            "document_form.html",
        ]:
            with self.subTest(name=name):
                content = (base / name).read_text(encoding="utf-8")
                self.assertIn("nj-invoice", content)
                self.assertIn("suppliers/partials/_design_system.html", content)

    def test_purchase_form_preserves_dynamic_item_contract(self):
        base = Path(__file__).resolve().parents[1] / "templates" / "suppliers"
        content = (base / "purchase_form.html").read_text(encoding="utf-8")
        self.assertIn('id="supplierPurchaseForm"', content)
        self.assertIn('id="supplierAddItem"', content)
        self.assertIn('id="supplierItemsBody"', content)
        self.assertIn('id="supplierEmptyItemTemplate"', content)
        self.assertIn("refreshSummary", content)
        self.assertIn("filterProducts", content)

    def test_status_tracks_only_color_the_committed_state(self):
        cases = [
            ("suppliers/partials/_supplier_status_track.html", "blocked", "Blocked"),
            ("suppliers/partials/_purchase_status_track.html", "pending", "Pending"),
            ("suppliers/partials/_purchase_payment_track.html", "partial", "Partially Paid"),
        ]
        for template_name, status, label in cases:
            with self.subTest(template_name=template_name):
                html = get_template(template_name).render(
                    {"current_status": status, "current_label": label}
                )
                self.assertEqual(html.count("is-current"), 1)
                self.assertIn(label, html)

    def test_supplier_tables_do_not_force_horizontal_scroll(self):
        design_system = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "suppliers"
            / "partials"
            / "_design_system.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("overflow-x:auto", design_system.replace(" ", ""))
        self.assertIn("table-layout:fixed", design_system.replace(" ", ""))
        self.assertIn("data-label", (Path(__file__).resolve().parents[1] / "templates" / "suppliers" / "supplier_list.html").read_text(encoding="utf-8"))
