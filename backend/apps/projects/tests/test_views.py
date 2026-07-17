from django.test import TestCase

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.projects.models import Project


class ProjectViewTest(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="project-view@example.com", password="test-pass-123"
        )
        self.company = Company.objects.create(name="Project View Company")
        self.client_record = Client.objects.create(
            id_company=self.company, name="Project View Client"
        )
        self.project = Project.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            name="Rendered Project",
            status="pending",
        )
        self.client.force_login(self.user)

    def test_project_pages_render_without_template_errors(self):
        urls = [
            "/projects/",
            "/projects/create/",
            f"/projects/{self.project.id_project}/",
            f"/projects/{self.project.id_project}/edit/",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_delete_get_redirects_to_detail_instead_of_rendering_old_template(self):
        response = self.client.get(f"/projects/{self.project.id_project}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/projects/{self.project.id_project}/", response.url)
