from datetime import date, timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.projects.forms import ProjectForm
from apps.projects.models import Project, ProjectEvidence, ProjectGalleryImage
from apps.inspections.models import InspectionAssignment, InspectionAssignmentGalleryImage


class ProjectWorkflowTemplateTests(SimpleTestCase):
    def test_templates_use_automatic_status_and_internal_action_modals(self):
        base = Path(__file__).resolve().parents[1] / "templates" / "projects"
        list_content = (base / "list.html").read_text(encoding="utf-8")
        detail_content = (base / "detail.html").read_text(encoding="utf-8")
        form_content = (base / "form.html").read_text(encoding="utf-8")
        modal_content = (base / "partials" / "_action_modal.html").read_text(encoding="utf-8")

        self.assertIn("interactive=False", list_content)
        self.assertIn('data-project-action="delete"', list_content)
        self.assertIn('data-project-action="cancel"', list_content)
        self.assertIn('data-project-action="approve"', detail_content)
        self.assertIn('data-project-action="close"', detail_content)
        self.assertIn("interactive_close=True", list_content + detail_content)
        self.assertIn("Approve and close", modal_content)
        self.assertIn('close:{title:"Close project?"', modal_content)
        self.assertNotIn("confirm(", list_content + detail_content)
        self.assertIn('name="save_mode" value="draft"', form_content)
        self.assertIn('name="save_mode" value="pending"', form_content)

    def test_project_form_excludes_manual_workflow_and_assignment_fields(self):
        self.assertNotIn("status", ProjectForm.Meta.fields)
        self.assertNotIn("end_date", ProjectForm.Meta.fields)
        self.assertNotIn("assigned_users", ProjectForm.Meta.fields)


class ProjectWorkflowEndpointTests(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="project-workflow@example.com", password="test-pass-123"
        )
        self.company = Company.objects.create(name="Project Workflow Company")
        self.client_record = Client.objects.create(
            id_company=self.company, name="Project Workflow Client"
        )
        self.project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Workflow Project",
            status="pending",
        )
        self.client.force_login(self.user)

    def add_evidence(self):
        return ProjectEvidence.objects.create(
            id_project=self.project,
            file=SimpleUploadedFile("project.webp", b"project-evidence", content_type="image/webp"),
            description="Finished work",
            uploaded_by=self.user,
        )


    def test_create_buttons_set_draft_or_pending_automatically(self):
        creator = UserAccount.objects.create_user(
            email="project-creator@example.com",
            password="test-pass-123",
            first_name="Creator",
            id_company=self.company,
            is_company_owner=True,
        )
        self.client.force_login(creator)
        base_data = {
            "id_client": self.client_record.id_client,
            "name": "Automatic Project",
            "contract_amount": "1500.00",
            "project_address": "123 Main St",
            "description": "Roof work",
        }
        draft_response = self.client.post(
            f"/{self.company.slug}/projects/create/", {**base_data, "save_mode": "draft"}
        )
        self.assertEqual(draft_response.status_code, 302)
        self.assertEqual(
            Project.objects.get(name="Automatic Project").status, "draft"
        )

        pending_response = self.client.post(
            f"/{self.company.slug}/projects/create/",
            {**base_data, "name": "Pending Project", "save_mode": "pending"},
        )
        self.assertEqual(pending_response.status_code, 302)
        self.assertEqual(Project.objects.get(name="Pending Project").status, "pending")

    def test_project_from_inspection_copies_data_but_not_photos(self):
        creator = UserAccount.objects.create_user(
            email="project-from-inspection@example.com",
            password="test-pass-123",
            first_name="Creator",
            id_company=self.company,
            is_company_owner=True,
        )
        inspection = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=creator,
            inspection_date=timezone.now() + timedelta(days=1),
            status="completed",
            notes="Inspection instructions",
            inspection_notes="Damage found",
            recommendations="Replace damaged shingles",
        )
        InspectionAssignmentGalleryImage.objects.create(
            assignment=inspection,
            category="after",
            file=SimpleUploadedFile(
                "inspection-source.webp", b"source-photo", content_type="image/webp"
            ),
            description="Inspection source photo",
            uploaded_by=creator,
        )
        self.client.force_login(creator)
        response = self.client.post(
            f"/{self.company.slug}/projects/inspections/{inspection.id_assignment}/create/",
            {
                "name": "Project from inspection",
                "contract_amount": "900.00",
                "project_address": "Inspection address",
                "description": "Project scope",
                "project_notes": "Internal note",
                "save_mode": "pending",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name="Project from inspection")
        inspection.refresh_from_db()
        self.assertEqual(inspection.id_project_id, project.id_project)
        self.assertEqual(ProjectEvidence.objects.filter(id_project=project).count(), 0)
        self.assertEqual(ProjectGalleryImage.objects.filter(project=project).count(), 0)
        self.assertEqual(inspection.gallery_images.count(), 1)

    def test_manual_status_endpoint_is_disabled(self):
        response = self.client.post(
            f"/projects/{self.project.id_project}/status/",
            {"status": "in_progress"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "pending")


    def test_project_can_be_closed_manually_without_field_submission(self):
        response = self.client.post(f"/projects/{self.project.id_project}/close/")
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "completed")
        self.assertEqual(self.project.progress, 100)
        self.assertEqual(self.project.end_date, date.today())

    def test_project_can_be_deleted_before_field_submission(self):
        response = self.client.post(f"/projects/{self.project.id_project}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_project_cannot_be_deleted_after_field_submission(self):
        self.add_evidence()
        response = self.client.post(f"/projects/{self.project.id_project}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_project_can_be_cancelled_with_reason_after_submission(self):
        self.add_evidence()
        response = self.client.post(
            f"/projects/{self.project.id_project}/cancel/",
            {"cancel_reason": "Client stopped the work."},
        )
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "cancelled")
        self.assertEqual(self.project.cancellation_reason, "Client stopped the work.")

    def test_approval_closes_project_and_sets_final_date(self):
        self.add_evidence()
        self.project.status = "review"
        self.project.save(update_fields=["status"])
        response = self.client.post(f"/projects/{self.project.id_project}/approve/")
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "completed")
        self.assertEqual(self.project.progress, 100)
        self.assertEqual(self.project.end_date, date.today())
