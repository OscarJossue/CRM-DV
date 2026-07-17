from pathlib import Path

from django.test import SimpleTestCase


class ClientUiTemplateTests(SimpleTestCase):
    def test_list_uses_unified_search_and_invoice_style_components(self):
        path = Path(__file__).resolve().parents[1] / "templates/clients/list.html"
        content = path.read_text(encoding="utf-8")

        self.assertIn('name="q"', content)
        self.assertNotIn('name="code"', content)
        self.assertNotIn('name="name"', content)
        self.assertNotIn('name="dni"', content)
        self.assertNotIn("filterPhone", content)
        self.assertNotIn("filterEmail", content)
        self.assertIn("crm-code-link", content)
        self.assertNotIn("client-summary-cards", content)
        self.assertNotIn("client-chart", content)
        self.assertIn("nj-icon-btn", content)
        self.assertIn("client-delete-modal", content)


class ClientFormUiTests(SimpleTestCase):
    def test_internal_notes_are_removed_from_client_form(self):
        path = Path(__file__).resolve().parents[1] / "templates/clients/form.html"
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("form.notes", content)
        self.assertNotIn("Internal notes", content)
