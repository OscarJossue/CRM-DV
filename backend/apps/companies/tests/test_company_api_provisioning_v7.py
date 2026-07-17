from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.companies.models import Company
from apps.platform_plans.models import PlatformPlan


class CompanyAPIProvisioningV7Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.root = UserAccount.objects.create_superuser(
            email="api-root@example.com",
            password="Root-pass-2026!",
            first_name="Root",
        )
        self.client.force_authenticate(self.root)
        self.plan = PlatformPlan.objects.create(
            name="API Business",
            code="api-business",
            price="149.00",
            max_users=25,
            status="active",
        )

    def payload(self, **overrides):
        start = timezone.localdate()
        data = {
            "name": "API Tenant",
            "legal_name": "API Tenant LLC",
            "email": "office@api-tenant.test",
            "id_plan": self.plan.id_plan,
            "start_date": start.isoformat(),
            "renewal_date": (start + timedelta(days=30)).isoformat(),
            "admin_first_name": "API",
            "admin_last_name": "Administrator",
            "admin_email": "admin@api-tenant.test",
            "admin_password": "Tenant-pass-2026!",
        }
        data.update(overrides)
        return data

    def test_api_creation_is_atomic_and_always_creates_company_admin(self):
        response = self.client.post("/api/companies/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)

        company = Company.objects.get(name="API Tenant")
        administrator = UserAccount.objects.get(email="admin@api-tenant.test")
        self.assertEqual(administrator.id_company_id, company.id_company)
        self.assertTrue(administrator.is_company_owner)
        self.assertFalse(administrator.is_staff)
        self.assertFalse(administrator.is_superuser)
        self.assertTrue(administrator.check_password("Tenant-pass-2026!"))
        self.assertEqual(company.platform_subscriptions.count(), 1)

    def test_api_rejects_company_without_administrator_credentials(self):
        payload = self.payload()
        payload.pop("admin_password")
        response = self.client.post("/api/companies/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Company.objects.filter(name="API Tenant").exists())
