from datetime import timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.inspections.forms import InspectionAssignmentForm
from apps.inspections.models import InspectionAssignment, InspectionAssignmentGalleryImage


class InspectionWorkflowTemplateTests(SimpleTestCase):
    def test_templates_use_automatic_status_and_internal_action_modals(self):
        base = Path(__file__).resolve().parents[1] / "templates" / "inspections"
        list_content = (base / "assignment_list.html").read_text(encoding="utf-8")
        detail_content = (base / "assignment_detail.html").read_text(encoding="utf-8")
        form_content = (base / "assignment_form.html").read_text(encoding="utf-8")
        modal_content = (base / "partials" / "_action_modal.html").read_text(encoding="utf-8")

        self.assertIn("interactive=False", list_content)
        self.assertIn('data-inspection-action="delete"', list_content)
        self.assertIn('data-inspection-action="cancel"', list_content)
        self.assertIn('data-inspection-action="approve"', detail_content)
        self.assertIn('data-inspection-action="complete"', detail_content)
        self.assertIn("interactive_close=True", list_content + detail_content)
        self.assertIn("Close and create project", modal_content)
        self.assertNotIn("confirm(", list_content + detail_content)
        self.assertIn('name="save_mode" value="draft"', form_content)
        self.assertIn('name="save_mode" value="pending"', form_content)
        self.assertNotIn("temp_client_notes", form_content)

    def test_inspection_form_excludes_manual_status_and_client_notes(self):
        self.assertNotIn("status", InspectionAssignmentForm.Meta.fields)
        self.assertNotIn("inspection_notes", InspectionAssignmentForm.Meta.fields)
        self.assertNotIn("temp_client_notes", InspectionAssignmentForm.declared_fields)


class InspectionWorkflowEndpointTests(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="inspection-workflow@example.com", password="test-pass-123"
        )
        self.company = Company.objects.create(name="Inspection Workflow Company")
        self.client_record = Client.objects.create(
            id_company=self.company, name="Inspection Workflow Client"
        )
        self.assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.user,
            inspection_date=timezone.now() + timedelta(days=1),
            status="pending",
        )
        self.client.force_login(self.user)

    def add_evidence(self):
        return InspectionAssignmentGalleryImage.objects.create(
            assignment=self.assignment,
            category="after",
            file=SimpleUploadedFile("inspection.webp", b"inspection-evidence", content_type="image/webp"),
            description="Roof evidence",
            uploaded_by=self.user,
        )


    def test_create_buttons_set_draft_or_pending_automatically(self):
        creator = UserAccount.objects.create_user(
            email="inspection-creator@example.com",
            password="test-pass-123",
            first_name="Creator",
            id_company=self.company,
            is_company_owner=True,
        )
        self.client.force_login(creator)
        date_value = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        base_data = {
            "client": self.client_record.id_client,
            "inspector": creator.pk,
            "inspection_date": date_value,
            "google_maps_url": "https://maps.google.com/?q=test",
            "notes": "Inspect roof",
        }
        draft_response = self.client.post(
            f"/{self.company.slug}/inspections/create/", {**base_data, "save_mode": "draft"}
        )
        self.assertEqual(draft_response.status_code, 302)
        self.assertTrue(
            InspectionAssignment.objects.filter(
                client=self.client_record, status="draft"
            ).exists()
        )

        pending_response = self.client.post(
            f"/{self.company.slug}/inspections/create/", {**base_data, "save_mode": "pending"}
        )
        self.assertEqual(pending_response.status_code, 302)
        self.assertGreaterEqual(
            InspectionAssignment.objects.filter(
                client=self.client_record, status="pending"
            ).count(),
            2,
        )

    def test_manual_status_endpoint_is_disabled(self):
        response = self.client.post(
            f"/inspections/{self.assignment.id_assignment}/status/",
            {"status": "in_progress"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "pending")


    def test_inspection_can_be_closed_manually_without_field_submission(self):
        response = self.client.post(
            f"/inspections/{self.assignment.id_assignment}/close/"
        )
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "completed")
        self.assertIsNotNone(self.assignment.audit_completed_at)

    def test_close_and_create_project_redirects_to_project_form(self):
        response = self.client.post(
            f"/inspections/{self.assignment.id_assignment}/close/",
            {"next": "project"},
        )
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "completed")
        self.assertIn(
            f"/projects/inspections/{self.assignment.id_assignment}/create/",
            response.url,
        )

    def test_inspection_can_be_deleted_before_field_submission(self):
        response = self.client.post(f"/inspections/{self.assignment.id_assignment}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(InspectionAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_inspection_cannot_be_deleted_after_field_submission(self):
        self.add_evidence()
        response = self.client.post(f"/inspections/{self.assignment.id_assignment}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(InspectionAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_inspection_can_be_cancelled_with_reason_after_submission(self):
        self.add_evidence()
        response = self.client.post(
            f"/inspections/{self.assignment.id_assignment}/cancel/",
            {"cancel_reason": "Access to the property was revoked."},
        )
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, "cancelled")
        self.assertEqual(
            self.assignment.cancellation_reason,
            "Access to the property was revoked.",
        )
