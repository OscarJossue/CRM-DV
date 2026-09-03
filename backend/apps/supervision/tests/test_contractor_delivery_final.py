from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Role, RolePermission, UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.inspections.models import InspectionAssignment
from apps.projects.models import Project, ProjectAssignment


class ContractorDeliveryFinalTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()

        self.company = Company.objects.create(name="Final Contractor Flow")
        self.role = Role.objects.create(
            id_company=self.company,
            name="Contractor Only",
            is_contractor_only=True,
        )
        for module in ("inspections", "projects"):
            RolePermission.objects.create(
                id_role=self.role,
                module=module,
                can_view=True,
            )
        self.contractor = UserAccount.objects.create_user(
            email="field-final@example.com",
            password="test-pass-123",
            first_name="Field",
            last_name="User",
            id_company=self.company,
            id_role=self.role,
        )
        self.owner = UserAccount.objects.create_user(
            email="owner-final@example.com",
            password="test-pass-123",
            first_name="Company",
            last_name="Owner",
            id_company=self.company,
            is_company_owner=True,
        )
        self.client_record = Client.objects.create(
            id_company=self.company,
            name="Mobile Client",
            address="100 Main Street, Miami, FL",
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()
        super().tearDown()

    @staticmethod
    def image_upload(name="phone-camera.jpg", size=(2400, 1800)):
        buffer = BytesIO()
        Image.new("RGB", size, (160, 90, 40)).save(buffer, format="JPEG", quality=95)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def test_inspection_single_submit_saves_notes_webp_description_and_review(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
            google_maps_url="https://maps.google.com/?q=100+Main+Street",
        )
        self.client.force_login(self.contractor)
        url = reverse(
            "company_inspections:inspection_submit_audit",
            kwargs={"company_slug": self.company.slug, "id_assignment": assignment.id_assignment},
        )
        response = self.client.post(
            url,
            {
                "inspection_notes": "Roof edge inspected and documented.",
                "recommendations": "Replace the damaged flashing.",
                "description_1": "North edge flashing damage",
                "photo_1": self.image_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "review")
        self.assertEqual(assignment.gallery_images.count(), 1)
        photo = assignment.gallery_images.get()
        self.assertTrue(photo.file.name.endswith(".webp"))
        self.assertEqual(photo.description, "North edge flashing damage")
        with Image.open(photo.file.path) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertLessEqual(max(image.size), 1600)

    def test_project_single_submit_uses_webp_and_optional_description(self):
        project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Mobile Project",
            google_maps_url="https://maps.google.com/?q=100+Main+Street",
        )
        ProjectAssignment.objects.create(id_project=project, id_user=self.contractor)
        self.client.force_login(self.contractor)
        url = reverse(
            "company_projects:project_submit_audit",
            kwargs={"company_slug": self.company.slug, "id_project": project.id_project},
        )
        response = self.client.post(
            url,
            {
                "contractor_observations": "The assigned repair is complete.",
                "contractor_recommendations": "",
                "description_1": "",
                "photo_1": self.image_upload("project.png", size=(1900, 1200)),
            },
        )
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.status, "review")
        evidence = project.evidence.get()
        self.assertTrue(evidence.file.name.endswith(".webp"))
        self.assertIsNone(evidence.description)
        with Image.open(evidence.file.path) as image:
            self.assertEqual(image.format, "WEBP")

    def test_contractor_generic_detail_redirects_to_unified_responsive_portal(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
            status="in_progress",
        )
        self.client.force_login(self.contractor)

        generic_url = reverse(
            "company_inspections:inspection_detail",
            kwargs={"company_slug": self.company.slug, "id_assignment": assignment.id_assignment},
        )
        portal_url = reverse(
            "company_contractor_portal:inspection_detail",
            kwargs={"company_slug": self.company.slug, "id_assignment": assignment.id_assignment},
        )

        mobile_response = self.client.get(
            generic_url,
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile",
        )
        self.assertRedirects(
            mobile_response,
            portal_url,
            fetch_redirect_response=False,
        )

        desktop_response = self.client.get(
            generic_url,
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        self.assertRedirects(
            desktop_response,
            portal_url,
            fetch_redirect_response=False,
        )

        # The contractor portal is now one responsive template for both device
        # classes instead of maintaining separate mobile/desktop templates.
        portal_mobile = self.client.get(
            portal_url,
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile",
        )
        self.assertEqual(portal_mobile.status_code, 200)
        self.assertTemplateUsed(portal_mobile, "contractor_portal/inspection_detail.html")

        portal_desktop = self.client.get(
            portal_url,
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        self.assertEqual(portal_desktop.status_code, 200)
        self.assertTemplateUsed(portal_desktop, "contractor_portal/inspection_detail.html")

    def test_completed_inspection_can_create_a_linked_project_with_maps(self):
        assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.contractor,
            inspection_date=timezone.now(),
            status="completed",
            notes="Replace damaged shingles.",
            inspection_notes="Measured the affected area.",
            recommendations="Use architectural shingles.",
            google_maps_url="https://maps.google.com/?q=100+Main+Street",
        )
        self.client.force_login(self.owner)
        url = reverse(
            "company_projects:project_create_from_inspection",
            kwargs={"company_slug": self.company.slug, "id_assignment": assignment.id_assignment},
        )
        response = self.client.post(
            url,
            {
                "name": "Project created from inspection",
                "project_address": self.client_record.address,
                "google_maps_url": assignment.google_maps_url,
                "description": assignment.inspection_notes,
                "project_notes": assignment.recommendations,
                "status": "pending",
                "contract_amount": "0.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.id_project_id)
        self.assertEqual(assignment.id_project.id_client_id, self.client_record.id_client)
        self.assertEqual(assignment.id_project.google_maps_url, assignment.google_maps_url)
