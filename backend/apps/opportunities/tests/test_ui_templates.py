from datetime import date
from pathlib import Path

from django import forms
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Role, UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.opportunities.forms import LeadForm


class OpportunityUiTemplateTests(SimpleTestCase):
    def test_list_uses_unified_search_and_invoice_style_status_workflow(self):
        base = Path(__file__).resolve().parents[1] / "templates/opportunities"
        content = (base / "list.html").read_text(encoding="utf-8")

        self.assertIn('name="q"', content)
        self.assertIn('name="status"', content)
        self.assertNotIn('name="source"', content)
        self.assertNotIn('name="code"', content)
        self.assertNotIn('name="name"', content)
        self.assertNotIn('name="dni"', content)
        self.assertIn("crm-status-grid", content)
        self.assertIn('_status_track.html', content)
        self.assertIn("nj-icon-btn", content)
        self.assertIn("interactive=True", content)
        self.assertIn("data-opportunity-status-workflow", content)
        self.assertIn("statusUpdateUrl", content)
        self.assertIn("showHoverLabel", content)
        self.assertIn("clearHoverLabel", content)
        self.assertIn("renderCommittedState", content)
        self.assertIn("status === workflow.dataset.currentStatus", content)
        self.assertIn("Click changes the selected ball immediately", content)
        self.assertNotIn("renderPreviewState", content)
        self.assertNotIn("is-previewing", content)
        self.assertNotIn("is-preview-active", content)
        self.assertNotIn("document.addEventListener('pointermove'", content)
        self.assertNotIn("document.addEventListener('mousemove'", content)

    def test_status_partial_has_all_workflow_stages_and_invoice_components(self):
        base = Path(__file__).resolve().parents[1] / "templates/opportunities/partials"
        content = (base / "_status_track.html").read_text(encoding="utf-8")

        for stage in ("new", "qualified", "won", "converted", "cancelled"):
            self.assertIn(stage, content)

        self.assertIn("nj-workflow", content)
        self.assertIn("nj-status-track", content)
        self.assertIn("nj-status-node", content)
        self.assertIn("nj-status-line", content)
        self.assertIn("nj-status-caption", content)
        self.assertIn("data-opportunity-status-node", content)
        self.assertIn("data-status-value", content)
        self.assertIn("data-current-label", content)
        self.assertIn("data-opportunity-status-caption", content)
        self.assertIn("data-opportunity-status-hover-caption", content)
        self.assertNotIn("is-preview", content)


class OpportunityFormTemplateRegressionTests(SimpleTestCase):
    def test_opportunity_form_uses_native_selects_and_native_date_control(self):
        template = Path(__file__).resolve().parents[1] / "templates" / "opportunities" / "form.html"
        content = template.read_text(encoding="utf-8")

        self.assertNotIn("data-opportunity-choice", content)
        self.assertNotIn("opportunity-choice-menu", content)
        self.assertIn("{{ form.status }}", content)
        self.assertIn("{{ form.source }}", content)
        self.assertIn("{{ form.next_follow_up_date }}", content)
        self.assertIn("data-open-date-picker", content)
        self.assertIn("opportunity-calendar-button", content)
        self.assertIn("showPicker", content)
        self.assertIn("::-webkit-calendar-picker-indicator", content)
        self.assertIn("Next follow-up date", content)
        self.assertNotIn("Internal notes", content)
        self.assertNotIn("date and time", content)

    def test_client_search_is_enhanced_without_body_level_dropdown(self):
        template = Path(__file__).resolve().parents[1] / "templates" / "opportunities" / "form.html"
        content = template.read_text(encoding="utf-8")

        self.assertIn("new TomSelect", content)
        self.assertIn("'client_code'", content)
        self.assertIn("'name'", content)
        self.assertIn("'dni'", content)
        self.assertIn("searchField: ['client_code', 'name', 'dni']", content)
        self.assertNotIn("searchField: ['client_code', 'name', 'dni', 'email'", content)
        self.assertNotIn("dropdownParent", content)
        self.assertIn("clientPreview", content)

    def test_status_source_and_follow_up_widgets_submit_real_values(self):
        status_field = LeadForm.base_fields["status"]
        source_field = LeadForm.base_fields["source"]
        follow_up_field = LeadForm.base_fields["next_follow_up_date"]

        self.assertIsInstance(status_field.widget, forms.Select)
        self.assertNotIsInstance(status_field.widget, forms.HiddenInput)
        self.assertIsInstance(source_field.widget, forms.Select)
        self.assertNotIsInstance(source_field.widget, forms.HiddenInput)
        self.assertIsInstance(follow_up_field, forms.DateField)
        self.assertEqual(follow_up_field.widget.input_type, "date")


class OpportunityFormSaveRegressionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Opportunity Form Company")
        self.role = Role.objects.create(id_company=self.company, name="Sales")
        self.user = UserAccount.objects.create_user(
            email="sales-opportunity@example.com",
            password="test-pass-123",
            first_name="Sales",
            id_company=self.company,
            id_role=self.role,
        )
        self.client_record = Client.objects.create(
            id_company=self.company,
            name="Opportunity Client",
            dni="1717171717",
            email="client@example.com",
            phone="0999999999",
            address="Main Street 123",
        )

    def test_client_options_include_search_metadata(self):
        form = LeadForm(user=self.user)
        html = str(form["id_client"])

        self.assertIn("data-data=", html)
        self.assertIn("Opportunity Client", html)
        self.assertIn("1717171717", html)
        self.assertIn("client@example.com", html)
        self.assertIn("0999999999", html)
        self.assertIn(self.client_record.client_code, html)

    def test_real_selects_and_date_are_saved(self):
        form = LeadForm(
            data={
                "id_client": self.client_record.pk,
                "status": "qualified",
                "source": "website",
                "next_follow_up_date": "14/07/2026",
                "approximate_value": "1500.50",
                "project_description": "Roofing opportunity",
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        opportunity = form.save()
        opportunity.refresh_from_db()

        self.assertEqual(opportunity.status, "qualified")
        self.assertEqual(opportunity.source, "website")
        self.assertEqual(opportunity.next_follow_up_date.date(), date(2026, 7, 14))
        self.assertEqual(opportunity.id_client, self.client_record)
