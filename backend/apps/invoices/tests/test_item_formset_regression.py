from django.test import TestCase

from apps.clients.models import Client
from apps.companies.models import Company
from apps.invoices.forms import InvoiceItemFormSet
from apps.invoices.models import Invoice, InvoiceItem
from apps.invoices.views import get_invoice_item_formset_class


class InvoiceItemFormsetRegressionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Invoice Formset Test")
        self.client = Client.objects.create(
            id_company=self.company,
            name="Test Client",
        )
        self.invoice = Invoice.objects.create(
            id_company=self.company,
            id_client=self.client,
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            description="Roof labor",
            quantity="1.00",
            unit_price="10.00",
        )

    def test_existing_draft_item_accepts_post_with_custom_primary_key(self):
        prefix = InvoiceItemFormSet.get_default_prefix()
        data = {
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-MIN_NUM_FORMS": "1",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-id_invoice_item": str(self.item.pk),
            f"{prefix}-0-invoice": str(self.invoice.pk),
            f"{prefix}-0-description": "Roof labor updated",
            f"{prefix}-0-quantity": "1.00",
            f"{prefix}-0-unit_price": "10.00",
        }

        formset = InvoiceItemFormSet(data=data, instance=self.invoice)

        self.assertTrue(formset.is_valid(), formset.errors)

    def test_one_initial_item_does_not_create_a_second_blank_row(self):
        formset_class = get_invoice_item_formset_class(extra=0)
        formset = formset_class(
            initial=[
                {
                    "description": "Roof labor",
                    "quantity": "1.00",
                    "unit_price": "10.00",
                }
            ],
            queryset=InvoiceItem.objects.none(),
        )

        self.assertEqual(formset.total_form_count(), 1)

    def test_empty_create_formset_renders_exactly_one_required_row(self):
        formset_class = get_invoice_item_formset_class(extra=0)
        formset = formset_class(queryset=InvoiceItem.objects.none())

        self.assertEqual(formset.initial_form_count(), 0)
        self.assertEqual(formset.total_form_count(), 1)
        self.assertEqual(len(formset.forms), 1)
