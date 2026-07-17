from datetime import timedelta

from django.contrib.auth.hashers import identify_hasher
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import CRMLoginForm
from apps.accounts.models import Role, RolePermission, UserAccount
from apps.company_modules.models import CompanyModule
from apps.platform_plans.models import PlatformPlan

from apps.companies.forms import CompanyProvisioningForm, get_company_owner_user
from apps.companies.models import Company
from apps.companies.services import get_tenant_module_codes, provision_company_with_admin


class CompanyProvisioningV7Tests(TestCase):
    def setUp(self):
        self.plan = PlatformPlan.objects.create(
            name="Business Monthly",
            code="business",
            price="99.00",
            max_users=30,
            status="active",
        )
        self.start_date = timezone.localdate()
        self.renewal_date = self.start_date + timedelta(days=30)

    def valid_form_data(self, **overrides):
        data = {
            "name": "Peluche Services",
            "legal_name": "Peluche Services LLC",
            "email": "office@peluche.test",
            "phone": "555-1000",
            "address": "100 Main St",
            "city": "Miami",
            "state": "FL",
            "country": "United States",
            "description": "Tenant created from the company module.",
            "id_plan": str(self.plan.id_plan),
            "start_date": self.start_date.isoformat(),
            "renewal_date": self.renewal_date.isoformat(),
            "admin_first_name": "Peluche",
            "admin_last_name": "Admin",
            "admin_email": "peluche@demo.com",
            "admin_phone": "555-2000",
            "password1": "admin12345",
            "password2": "admin12345",
        }
        data.update(overrides)
        return data

    def provision(self):
        return provision_company_with_admin(
            company_data={
                "name": "Peluche Services",
                "legal_name": "Peluche Services LLC",
                "email": "office@peluche.test",
                "phone": "555-1000",
                "address": "100 Main St",
                "city": "Miami",
                "state": "FL",
                "country": "United States",
                "description": "Tenant created from the company module.",
            },
            admin_data={
                "first_name": "Peluche",
                "last_name": "Admin",
                "email": "PELUCHE@DEMO.COM",
                "phone": "555-2000",
                "password": "admin12345",
            },
            subscription_data={
                "id_plan": self.plan,
                "start_date": self.start_date,
                "renewal_date": self.renewal_date,
            },
        )

    def test_form_validates_both_steps_and_normalizes_admin_email(self):
        form = CompanyProvisioningForm(data=self.valid_form_data(admin_email="PELuChe@Demo.Com"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["admin_email"], "peluche@demo.com")

    def test_invalid_second_step_does_not_create_partial_company(self):
        form = CompanyProvisioningForm(data=self.valid_form_data(password2="different123"))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.first_error_step(), 2)
        self.assertFalse(Company.objects.filter(name="Peluche Services").exists())

    def test_service_creates_active_company_and_tenant_administrator_atomically(self):
        result = self.provision()
        company = result["company"]
        admin = result["administrator"]

        self.assertEqual(company.status, "active")
        self.assertEqual(admin.email, "peluche@demo.com")
        self.assertTrue(admin.is_company_owner)
        self.assertTrue(admin.is_active)
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.check_password("admin12345"))
        self.assertNotEqual(admin.password, "admin12345")
        identify_hasher(admin.password)

        tenant_modules = set(get_tenant_module_codes())
        permission_modules = set(
            RolePermission.objects.filter(id_role=admin.id_role).values_list("module", flat=True)
        )
        enabled_modules = set(
            CompanyModule.objects.filter(id_company=company, is_enabled=True).values_list("module", flat=True)
        )
        self.assertEqual(permission_modules, tenant_modules)
        self.assertEqual(enabled_modules, tenant_modules)
        self.assertFalse(any(code.startswith("platform_") for code in permission_modules))
        self.assertNotIn("companies", permission_modules)
        self.assertNotIn("company_modules", permission_modules)

    def test_new_company_administrator_can_login(self):
        result = self.provision()
        request = self.client.request().wsgi_request
        form = CRMLoginForm(
            request=request,
            data={"username": result["administrator"].email, "password": "admin12345"},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_create_view_is_two_step_and_legacy_onboarding_redirects(self):
        root = UserAccount.objects.create_superuser(
            email="root@example.com",
            password="root-password-123",
            first_name="Root",
        )
        self.client.force_login(root)

        response = self.client.get(reverse("companies:company_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-step-window="1"')
        self.assertContains(response, 'data-step-window="2"')
        self.assertContains(response, "Company administrator")

        legacy = self.client.get(reverse("companies:company_onboarding"))
        self.assertEqual(legacy.status_code, 200)
        self.assertContains(legacy, 'data-step-window="1"')
        self.assertContains(legacy, 'data-step-window="2"')

    def test_invalid_post_to_create_view_leaves_no_company(self):
        root = UserAccount.objects.create_superuser(
            email="root2@example.com",
            password="root-password-123",
            first_name="Root",
        )
        self.client.force_login(root)
        response = self.client.post(
            reverse("companies:company_create"),
            data=self.valid_form_data(password2="wrong-password"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Company.objects.filter(name="Peluche Services").exists())


    def test_staff_user_is_never_guessed_as_missing_company_administrator(self):
        company = Company.objects.create(name="Legacy Tenant Without Owner")
        staff_role = Role.objects.create(id_company=company, name="Staff")
        UserAccount.objects.create_user(
            email="staff-only@example.com",
            password="Staff-pass-2026!",
            first_name="Staff",
            id_company=company,
            id_role=staff_role,
            is_company_owner=False,
        )

        self.assertIsNone(get_company_owner_user(company))

    def test_audit_command_reassigns_single_owner_without_leaving_duplicates(self):
        company = Company.objects.create(name="Legacy Duplicate Owners", status="inactive")
        role = Role.objects.create(id_company=company, name="Owner")
        previous_owner = UserAccount.objects.create_user(
            email="previous-owner@example.com",
            password="Previous-pass-2026!",
            first_name="Previous",
            id_company=company,
            id_role=role,
            is_company_owner=True,
        )
        selected_admin = UserAccount.objects.create_user(
            email="selected-admin@example.com",
            password="Selected-pass-2026!",
            first_name="Selected",
            id_company=company,
            id_role=role,
            is_company_owner=False,
        )

        call_command(
            "audit_company_access",
            company_id=company.id_company,
            fix=True,
            activate=True,
            admin_email=selected_admin.email,
            password="Replacement-pass-2026!",
            verbosity=0,
        )

        previous_owner.refresh_from_db()
        selected_admin.refresh_from_db()
        company.refresh_from_db()
        self.assertFalse(previous_owner.is_company_owner)
        self.assertTrue(selected_admin.is_company_owner)
        self.assertTrue(selected_admin.check_password("Replacement-pass-2026!"))
        self.assertEqual(company.status, "active")
        self.assertEqual(
            UserAccount.objects.filter(id_company=company, is_company_owner=True).count(),
            1,
        )

    def test_successful_post_creates_company_admin_and_subscription(self):
        root = UserAccount.objects.create_superuser(
            email="root3@example.com",
            password="root-password-123",
            first_name="Root",
        )
        self.client.force_login(root)
        response = self.client.post(reverse("companies:company_create"), data=self.valid_form_data())
        company = Company.objects.get(name="Peluche Services")
        admin = UserAccount.objects.get(email="peluche@demo.com")
        self.assertRedirects(
            response,
            reverse("companies:company_detail", kwargs={"id_company": company.id_company}),
            fetch_redirect_response=False,
        )
        self.assertEqual(admin.id_company_id, company.id_company)
        self.assertTrue(admin.is_company_owner)
        self.assertEqual(company.platform_subscriptions.count(), 1)

    def test_company_update_keeps_owner_active_without_name_error(self):
        result = self.provision()
        company = result["company"]
        administrator = result["administrator"]
        root = UserAccount.objects.create_superuser(
            email="root-update@example.com",
            password="root-password-123",
            first_name="Root",
        )
        self.client.force_login(root)

        response = self.client.post(
            reverse("companies:company_update", kwargs={"id_company": company.id_company}),
            data={
                "name": company.name,
                "legal_name": company.legal_name or "",
                "email": company.email or "",
                "phone": company.phone or "",
                "address": company.address or "",
                "city": company.city or "",
                "state": company.state or "",
                "country": company.country or "",
                "description": company.description or "",
                "status": "active",
                "id_plan": str(self.plan.id_plan),
                "subscription_start_date": self.start_date.isoformat(),
                "subscription_renewal_date": self.renewal_date.isoformat(),
                "subscription_notes": "Updated safely",
                "owner_first_name": administrator.first_name,
                "owner_last_name": administrator.last_name or "",
                "owner_email": administrator.email,
                "owner_phone": administrator.phone or "",
                "owner_password1": "",
                "owner_password2": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        administrator.refresh_from_db()
        self.assertEqual(administrator.status, "active")
        self.assertTrue(administrator.is_active)
        self.assertTrue(administrator.is_company_owner)
