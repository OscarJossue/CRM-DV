from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.services import sync_role_permissions_from_post
from apps.clients.models import Client
from apps.companies.models import Company
from apps.estimates.forms import EstimateForm
from apps.estimates.models import Estimate
from apps.inspections.forms import InspectionAssignmentForm
from apps.inspections.models import InspectionAssignment, InspectionAssignmentGalleryImage
from apps.inspections.services import (
    approve_inspection_assignment,
    submit_inspection_assignment_for_review,
)
from apps.inspections.views import (
    InspectionAssignmentUpdateView,
    inspection_assignment_queryset_for_user,
)
from apps.projects.forms import ProjectForm
from apps.projects.models import Project, ProjectAssignment, ProjectEvidence, ProjectNote
from apps.projects.serializers import ProjectSerializer
from apps.projects.selectors import project_list_for_user
from apps.projects.services import (
    request_project_corrections,
    submit_project_for_review,
)
from apps.supervision.models import Supervision
from apps.supervision.serializers import SupervisionSerializer


class ContractorAuditWorkflowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Audit Workflow Company")
        self.other_company = Company.objects.create(name="Other Audit Company")
        self.contractor_role = Role.objects.create(
            id_company=self.company,
            name="Field Contractor",
            is_contractor_only=True,
        )
        self.contractor = UserAccount.objects.create_user(
            email="contractor@example.com",
            password="test-pass-123",
            first_name="Field",
            last_name="Contractor",
            id_company=self.company,
            id_role=self.contractor_role,
        )
        self.client_record = Client.objects.create(
            id_company=self.company,
            name="Audit Client",
            address="123 Test Street",
        )
        self.other_client = Client.objects.create(
            id_company=self.other_company,
            name="Other Client",
        )
        self.owner = UserAccount.objects.create_user(
            email="workflow-owner@example.com",
            password="test-pass-123",
            first_name="Workflow",
            last_name="Owner",
            id_company=self.company,
            is_company_owner=True,
        )
        self.factory = RequestFactory()

    def test_contractor_role_permissions_are_forced_to_view_only_field_modules(self):
        sync_role_permissions_from_post(
            self.contractor_role,
            ["clients", "inspections", "projects", "supervision"],
            {},
        )
        permissions = {
            permission.module: permission
            for permission in RolePermission.objects.filter(id_role=self.contractor_role)
        }
        self.assertEqual(set(permissions), {"inspections", "projects"})
        for permission in permissions.values():
            self.assertTrue(permission.can_view)
            self.assertFalse(permission.can_create)
            self.assertFalse(permission.can_edit)
            self.assertFalse(permission.can_delete)
            self.assertFalse(permission.can_approve)

    def test_contractor_only_sees_assigned_projects_and_inspections(self):
        assigned_project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Assigned Project",
        )
        ProjectAssignment.objects.create(
            id_project=assigned_project,
            id_user=self.contractor,
        )
        Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Unassigned Project",
        )
        Project.objects.create(
            id_company=self.other_company,
            id_client=self.other_client,
            name="Foreign Project",
        )
        assigned_inspection = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now() + timedelta(days=1),
        )
        InspectionAssignment.objects.create(
            client=self.client_record,
            inspection_date=timezone.now() + timedelta(days=2),
        )

        self.assertEqual(
            list(project_list_for_user(self.contractor).values_list("id_project", flat=True)),
            [assigned_project.id_project],
        )
        self.assertEqual(
            list(
                inspection_assignment_queryset_for_user(self.contractor).values_list(
                    "id_assignment", flat=True
                )
            ),
            [assigned_inspection.id_assignment],
        )

    def test_inspection_submission_requires_evidence_and_review_approval_completes_it(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now() + timedelta(days=1),
            status="in_progress",
            inspection_notes="Roof damage documented and measured.",
        )
        InspectionAssignmentGalleryImage.objects.create(
            assignment=assignment,
            category="before",
            file=SimpleUploadedFile("inspection.jpg", b"inspection-photo"),
            uploaded_by=self.contractor,
        )

        submitted = submit_inspection_assignment_for_review(assignment, self.contractor)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "review")
        self.assertIsNotNone(assignment.submitted_for_audit_at)
        self.assertEqual(submitted.pk, assignment.pk)

        approve_inspection_assignment(assignment, self.owner)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "completed")
        self.assertIsNotNone(assignment.audit_completed_at)
        self.assertEqual(assignment.reviewed_by_id, self.owner.pk)

    def test_rejected_project_review_returns_work_for_corrections(self):
        project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Contractor Project",
            status="in_progress",
        )
        ProjectAssignment.objects.create(id_project=project, id_user=self.contractor)
        ProjectEvidence.objects.create(
            id_project=project,
            title="Completion evidence",
            file=SimpleUploadedFile("evidence.jpg", b"project-photo"),
            uploaded_by=self.contractor,
        )
        ProjectNote.objects.create(
            id_project=project,
            note="All assigned work was completed.",
            created_by=self.contractor,
        )

        submitted = submit_project_for_review(project, self.contractor)
        project.refresh_from_db()
        self.assertEqual(project.status, "review")
        self.assertEqual(submitted.pk, project.pk)
        last_submission = project.submitted_for_audit_at
        self.assertIsNotNone(last_submission)

        request_project_corrections(
            project,
            self.owner,
            "Add a clear photo of the final flashing.",
        )
        project.refresh_from_db()
        self.assertEqual(project.status, "in_progress")
        # The current review workflow intentionally preserves the last-submitted
        # timestamp as part of the audit trail when corrections are requested.
        self.assertEqual(project.submitted_for_audit_at, last_submission)
        self.assertEqual(
            project.review_notes,
            "Add a clear photo of the final flashing.",
        )
        self.assertEqual(project.reviewed_by_id, self.owner.pk)

    def test_completed_inspection_can_be_the_source_of_an_estimate(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
            status="completed",
            inspection_notes="Replace damaged shingles and underlayment.",
        )
        form = EstimateForm(
            data={
                "client_billing_name": self.client_record.name,
                "client_billing_email": "",
                "client_billing_phone": "",
                "client_billing_address": self.client_record.address,
                "project_name": "Roof repair from inspection",
                "project_address": self.client_record.address,
                "description": assignment.inspection_notes,
                "validity_days": 15,
                "tax_rate": "0.00",
                "discount_amount": "0.00",
            },
            user=self.contractor,
            inspection=assignment,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        estimate = form.save()
        self.assertEqual(estimate.id_inspection_assignment_id, assignment.id_assignment)
        self.assertEqual(estimate.id_client_id, self.client_record.id_client)
        self.assertEqual(estimate.id_company_id, self.company.id_company)
        self.assertIsNone(estimate.id_project_id)

    def test_company_owner_sees_all_company_projects_without_role_name_hacks(self):
        first = Project.objects.create(
            id_company=self.company, id_client=self.client_record, name="Owner Project One"
        )
        second = Project.objects.create(
            id_company=self.company, id_client=self.client_record, name="Owner Project Two"
        )
        self.assertEqual(
            set(project_list_for_user(self.owner).values_list("id_project", flat=True)),
            {first.id_project, second.id_project},
        )

    def test_manual_forms_and_api_cannot_skip_directly_to_review_or_completed(self):
        # Status is intentionally absent from the administrative forms. A forged
        # POST value is ignored and the model keeps its safe default status.
        project_form = ProjectForm(
            data={
                "id_client": self.client_record.id_client,
                "name": "Forged Direct Completion",
                "status": "completed",
                "contract_amount": "0.00",
            },
            user=self.owner,
        )
        self.assertTrue(project_form.is_valid(), project_form.errors.as_json())
        project = project_form.save()
        self.assertEqual(project.status, "draft")

        inspection_form = InspectionAssignmentForm(
            data={
                "client": self.client_record.id_client,
                "inspection_date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "status": "review",
            },
            user=self.owner,
        )
        self.assertTrue(inspection_form.is_valid(), inspection_form.errors.as_json())
        assignment = inspection_form.save()
        self.assertEqual(assignment.status, "draft")

        # API serializers expose status, so protected workflow states are
        # rejected explicitly there.
        serializer = ProjectSerializer(
            data={
                "id_company": self.company.id_company,
                "id_client": self.client_record.id_client,
                "name": "API Direct Completion",
                "status": "completed",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_audit_api_rejects_targets_not_waiting_for_review(self):
        project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Not Submitted",
            status="in_progress",
        )
        serializer = SupervisionSerializer(data={"id_project": project.id_project})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_contractor_cannot_open_generic_inspection_edit_form(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
        )
        request = self.factory.get(f"/inspections/{assignment.id_assignment}/edit/")
        request.user = self.contractor
        response = InspectionAssignmentUpdateView.as_view()(
            request, id_assignment=assignment.id_assignment
        )
        self.assertEqual(response.status_code, 403)

    def test_approved_estimate_conversion_links_inspection_to_created_project(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
            status="completed",
            inspection_notes="Approved inspection scope.",
        )
        estimate = Estimate.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            id_inspection_assignment=assignment,
            status="approved",
            project_name="Inspection Conversion Project",
            project_address=self.client_record.address or "123 Test Street",
            total="2500.00",
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/{self.company.slug}/estimates/{estimate.id_estimate}/project/create/",
            {
                "id_client": self.client_record.id_client,
                "name": "Inspection Conversion Project",
                "project_address": self.client_record.address or "123 Test Street",
                "description": "Created from completed inspection",
                "project_notes": "Source inspection retained",
                "status": "pending",
                "contract_amount": "2500.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        estimate.refresh_from_db()
        assignment.refresh_from_db()
        self.assertIsNotNone(estimate.id_project_id)
        self.assertEqual(assignment.id_project_id, estimate.id_project_id)
        self.assertEqual(estimate.status, "converted")

    def test_audit_records_remain_isolated_by_company(self):
        project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Company Project",
        )
        foreign_project = Project.objects.create(
            id_company=self.other_company,
            id_client=self.other_client,
            name="Foreign Project",
        )
        own_audit = Supervision.objects.create(id_project=project)
        Supervision.objects.create(id_project=foreign_project)

        from apps.supervision.selectors import supervision_list_for_user

        owner = UserAccount.objects.create_user(
            email="owner@example.com",
            password="test-pass-123",
            first_name="Company",
            last_name="Owner",
            id_company=self.company,
            is_company_owner=True,
        )
        self.assertEqual(
            list(supervision_list_for_user(owner).values_list("id_supervision", flat=True)),
            [own_audit.id_supervision],
        )
