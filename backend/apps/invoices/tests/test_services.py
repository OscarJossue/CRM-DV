from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.invoices.services import prepare_invoice_items_initial_from_project


class InvoiceProjectItemInitialTests(SimpleTestCase):
    def test_project_creates_one_editable_invoice_item(self):
        project = SimpleNamespace(
            name="Roof replacement",
            description="Remove and replace the existing roof",
            contract_amount=Decimal("8750.50"),
        )

        items = prepare_invoice_items_initial_from_project(project)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["description"], "Remove and replace the existing roof")
        self.assertEqual(items[0]["quantity"], Decimal("1.00"))
        self.assertEqual(items[0]["unit_price"], Decimal("8750.50"))

    def test_project_name_is_used_when_description_is_empty(self):
        project = SimpleNamespace(
            name="Gutter installation",
            description="",
            contract_amount=Decimal("1200"),
        )

        items = prepare_invoice_items_initial_from_project(project)

        self.assertEqual(items[0]["description"], "Gutter installation")
        self.assertEqual(items[0]["unit_price"], Decimal("1200.00"))
