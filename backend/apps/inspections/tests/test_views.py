from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.inspections.models import InspectionAssignment


class InspectionViewTest(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="inspection-view@example.com", password="test-pass-123"
        )
        self.company = Company.objects.create(name="Inspection View Company")
        self.client_record = Client.objects.create(
            id_company=self.company, name="Inspection View Client"
        )
        self.assignment = InspectionAssignment.objects.create(
            client=self.client_record,
            inspector=self.user,
            inspection_date=timezone.now() + timedelta(days=1),
            status="pending",
        )
        self.client.force_login(self.user)

    def test_inspection_pages_render_without_template_errors(self):
        urls = [
            "/inspections/",
            "/inspections/create/",
            f"/inspections/{self.assignment.id_assignment}/",
            f"/inspections/{self.assignment.id_assignment}/edit/",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_delete_get_redirects_to_list(self):
        response = self.client.get(
            f"/inspections/{self.assignment.id_assignment}/delete/"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/inspections/")
