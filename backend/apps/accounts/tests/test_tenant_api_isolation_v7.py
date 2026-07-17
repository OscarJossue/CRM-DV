from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserAccount
from apps.company_modules.models import CompanyModule
from apps.companies.models import Company


class TenantAPIIsolationV7Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="Tenant One", status="active")
        self.other_company = Company.objects.create(name="Tenant Two", status="active")
        self.owner_role = Role.objects.create(id_company=self.company, name="Owner")
        self.staff_role = Role.objects.create(id_company=self.company, name="Staff")
        self.other_role = Role.objects.create(id_company=self.other_company, name="Other Staff")
        CompanyModule.objects.create(id_company=self.company, module="users", is_enabled=True)
        self.owner = UserAccount.objects.create_user(
            email="owner@tenant-one.test",
            password="Owner-pass-2026!",
            first_name="Owner",
            id_company=self.company,
            id_role=self.owner_role,
            status="active",
            is_active=True,
            is_company_owner=True,
        )
        self.client.force_authenticate(self.owner)

    def test_tenant_cannot_create_user_in_another_company(self):
        response = self.client.post(
            "/api/users/",
            {
                "id_company": self.other_company.id_company,
                "id_role": self.other_role.id_role,
                "first_name": "Cross",
                "last_name": "Tenant",
                "email": "cross@example.com",
                "password": "Strong-pass-2026!",
                "status": "active",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserAccount.objects.filter(email="cross@example.com").exists())

    def test_tenant_cannot_escalate_new_user_to_platform_admin(self):
        response = self.client.post(
            "/api/users/",
            {
                "id_company": self.company.id_company,
                "id_role": self.staff_role.id_role,
                "first_name": "Safe",
                "last_name": "Staff",
                "email": "safe-staff@example.com",
                "password": "Strong-pass-2026!",
                "status": "active",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "is_company_owner": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = UserAccount.objects.get(email="safe-staff@example.com")
        self.assertEqual(user.id_company_id, self.company.id_company)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_company_owner)
