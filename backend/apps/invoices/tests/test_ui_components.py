from types import SimpleNamespace

from django.template.loader import get_template
from django.test import SimpleTestCase

from apps.invoices.forms import ClientSelect, ProjectSelect


class FakeChoiceValue:
    def __init__(self, instance):
        self.instance = instance

    def __str__(self):
        return str(self.instance.id_client)


class FakeProjectChoiceValue:
    def __init__(self, instance):
        self.instance = instance

    def __str__(self):
        return str(self.instance.id_project)


class InvoiceUIComponentTests(SimpleTestCase):
    def test_client_select_exposes_billing_metadata(self):
        client = SimpleNamespace(
            id_client=7,
            name="Acme Roofing",
            email="billing@acme.test",
            phone="5551234",
            dni="TX-778899",
            address="100 Main Street",
            city="Austin",
            state="TX",
        )
        widget = ClientSelect()
        option = widget.create_option(
            name="id_client",
            value=FakeChoiceValue(client),
            label="Acme Roofing",
            selected=True,
            index=0,
        )

        self.assertEqual(option["attrs"]["data-billing-name"], "Acme Roofing")
        self.assertEqual(option["attrs"]["data-billing-email"], "billing@acme.test")
        self.assertEqual(option["attrs"]["data-billing-phone"], "5551234")
        self.assertEqual(option["attrs"]["data-billing-dni"], "TX-778899")
        self.assertIn("100 Main Street", option["attrs"]["data-billing-address"])
        self.assertIn("Austin, TX", option["attrs"]["data-billing-address"])


    def test_project_select_exposes_item_autofill_metadata(self):
        project = SimpleNamespace(
            id_project=12,
            id_client_id=7,
            id_company_id=3,
            name="Roof replacement",
            project_address="100 Main Street",
            description="Remove and replace roof",
            contract_amount="8750.50",
        )
        widget = ProjectSelect()
        option = widget.create_option(
            name="id_project",
            value=FakeProjectChoiceValue(project),
            label="Roof replacement",
            selected=True,
            index=0,
        )

        self.assertEqual(option["attrs"]["data-project-description"], "Remove and replace roof")
        self.assertEqual(option["attrs"]["data-project-contract-amount"], "8750.50")

    def test_document_track_always_renders_all_stages(self):
        invoice = SimpleNamespace(
            status="sent",
            sent_at=True,
            get_status_display=lambda: "Sent",
        )
        html = get_template(
            "invoices/partials/_document_status_track.html"
        ).render({"invoice": invoice})

        self.assertEqual(html.count("nj-status-node"), 4)
        self.assertIn('title="Draft"', html)
        self.assertIn('title="Pending send"', html)
        self.assertIn('title="Sent"', html)
        self.assertIn('title="Void"', html)
        self.assertIn("is-success is-current", html)
        self.assertEqual(html.count("is-current"), 1)

    def test_document_track_uses_synced_pending_and_void_colors(self):
        pending_invoice = SimpleNamespace(
            status="pending_send",
            get_status_display=lambda: "Pending Send",
        )
        pending_html = get_template(
            "invoices/partials/_document_status_track.html"
        ).render({"invoice": pending_invoice})
        self.assertIn("is-blue is-current", pending_html)
        self.assertEqual(pending_html.count("is-current"), 1)

        void_invoice = SimpleNamespace(
            status="void",
            get_status_display=lambda: "Void",
        )
        void_html = get_template(
            "invoices/partials/_document_status_track.html"
        ).render({"invoice": void_invoice})
        self.assertIn("is-void is-current", void_html)
        self.assertEqual(void_html.count("is-current"), 1)

    def test_payment_track_always_renders_all_stages(self):
        invoice = SimpleNamespace(
            payment_status="partial",
            get_payment_status_display=lambda: "Partial",
        )
        html = get_template(
            "invoices/partials/_payment_status_track.html"
        ).render({"invoice": invoice})

        self.assertEqual(html.count("nj-status-node"), 5)
        self.assertIn('title="Unpaid"', html)
        self.assertIn('title="Partial"', html)
        self.assertIn('title="Paid"', html)
        self.assertIn('title="Overpaid"', html)
        self.assertIn('title="Void"', html)
        self.assertIn("is-warning is-current", html)
        self.assertEqual(html.count("is-current"), 1)

    def test_payment_track_uses_void_gray_state(self):
        invoice = SimpleNamespace(
            payment_status="void",
            get_payment_status_display=lambda: "Void",
        )
        html = get_template(
            "invoices/partials/_payment_status_track.html"
        ).render({"invoice": invoice})

        self.assertIn("is-void is-current", html)
        self.assertEqual(html.count("is-current"), 1)
