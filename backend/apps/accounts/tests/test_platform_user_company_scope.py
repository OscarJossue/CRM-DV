from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company
from apps.core.redirects import get_user_dashboard_url
from apps.platform_users.forms import PlatformUserCreateForm


class PlatformUserCompanyScopeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Tenant Company",
            status="active",
            plan="starter",
            user_limit=5,
        )
        self.role = Role.objects.create(
            id_company=self.company,
            name="Owner",
            status="active",
        )

    def test_createsuperuser_has_no_company_or_tenant_role(self):
        user = UserAccount.objects.create_superuser(
            email="root@example.com",
            password="StrongRootPassword123!",
            first_name="Root",
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertIsNone(user.id_company_id)
        self.assertIsNone(user.id_role_id)
        self.assertEqual(get_user_dashboard_url(user), "/crm/dashboard/")

    def test_tenant_manager_requires_company(self):
        with self.assertRaisesMessage(ValueError, "Company is required"):
            UserAccount.objects.create_user(
                email="orphan@example.com",
                password="StrongTenantPassword123!",
                first_name="Orphan",
            )

    def test_tenant_user_keeps_its_company_and_role(self):
        user = UserAccount.objects.create_user(
            email="owner@example.com",
            password="StrongTenantPassword123!",
            first_name="Owner",
            id_company=self.company,
            id_role=self.role,
        )

        self.assertEqual(user.id_company_id, self.company.id_company)
        self.assertEqual(user.id_role_id, self.role.id_role)
        self.assertFalse(user.is_staff)

    def test_database_rejects_tenant_user_without_company(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserAccount.objects.create(
                    email="invalid@example.com",
                    first_name="Invalid",
                    password="not-used",
                    is_staff=False,
                    is_superuser=False,
                )

    def test_platform_user_form_does_not_create_internal_company(self):
        form = PlatformUserCreateForm(
            data={
                "first_name": "Support",
                "last_name": "Agent",
                "email": "support@example.com",
                "phone": "",
                "status": "active",
                "is_active": "on",
                "password1": "StrongPlatformPassword123!",
                "password2": "StrongPlatformPassword123!",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

        before = Company.objects.count()
        user = form.save()

        self.assertEqual(Company.objects.count(), before)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(user.id_company_id)
        self.assertIsNone(user.id_role_id)
