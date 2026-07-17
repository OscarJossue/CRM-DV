from django.template.loader import get_template
from django.test import SimpleTestCase


class InvoiceTemplateIntegrityTests(SimpleTestCase):
    def test_invoice_templates_compile(self):
        templates = [
            "invoices/list.html",
            "invoices/form.html",
            "invoices/detail.html",
            "invoices/send.html",
            "invoices/partials/_design_system.html",
            "invoices/partials/_document_status_track.html",
            "invoices/partials/_payment_status_track.html",
        ]
        for template_name in templates:
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))
    def test_invoice_item_template_renders_all_hidden_formset_fields(self):
        template = get_template("invoices/form.html")
        source = template.template.source

        self.assertIn("item_form.hidden_fields", source)
        self.assertIn("item_formset.empty_form.hidden_fields", source)
        self.assertNotIn("{{ item_form.id }}", source)


    def test_invoice_template_contains_project_item_sync(self):
        source = get_template("invoices/form.html").template.source

        self.assertIn("syncFirstItemFromProject", source)
        self.assertIn("projectContractAmount", source)
        self.assertIn('data-is-bound', source)
