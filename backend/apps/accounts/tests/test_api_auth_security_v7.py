from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company


class APIAuthenticationSecurityV7Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="JWT Tenant", status="active")
        self.role = Role.objects.create(id_company=self.company, name="Owner")
        self.user = UserAccount.objects.create_user(
            email="jwt-admin@example.com",
            password="Strong-pass-2026!",
            first_name="JWT",
            id_company=self.company,
            id_role=self.role,
            status="active",
            is_active=True,
            is_company_owner=True,
        )

    def issue_tokens(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": "Strong-pass-2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_active_company_user_can_obtain_tokens(self):
        data = self.issue_tokens()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_inactive_company_cannot_obtain_tokens(self):
        self.company.status = "inactive"
        self.company.save(update_fields=["status"])
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": "Strong-pass-2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)

    def test_existing_access_and_refresh_tokens_stop_working_after_suspension(self):
        tokens = self.issue_tokens()
        self.company.status = "inactive"
        self.company.save(update_fields=["status"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 401)

        self.client.credentials()
        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 401)
