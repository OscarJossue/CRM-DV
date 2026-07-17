from django.test import TestCase
from django.urls import reverse

from apps.accounts.forms import UserAccountCreateForm
from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.selectors import user_account_list_for_user
from apps.companies.models import Company
from apps.core.redirects import get_user_dashboard_url


class TenantUserAccessHotfixTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Tenant A",
            status="active",
            plan="starter",
            user_limit=2,
        )
        self.company_b = Company.objects.create(
            name="Tenant B",
            status="active",
            plan="starter",
            user_limit=5,
        )

        self.owner_role_a = Role.objects.create(
            id_company=self.company_a,
            name="Owner",
            status="active",
        )
        self.worker_role_a = Role.objects.create(
            id_company=self.company_a,
            name="Worker",
            status="active",
        )
        self.role_b = Role.objects.create(
            id_company=self.company_b,
            name="Tenant B Role",
            status="active",
        )

        self.owner_a = UserAccount.objects.create_user(
            email="owner-a@example.com",
            password="Owner-A-Strong-2026!",
            first_name="Owner A",
            id_company=self.company_a,
            id_role=self.owner_role_a,
            status="active",
            is_active=True,
            is_company_owner=True,
        )
        self.user_b = UserAccount.objects.create_user(
            email="user-b@example.com",
            password="User-B-Strong-2026!",
            first_name="User B",
            id_company=self.company_b,
            id_role=self.role_b,
            status="active",
            is_active=True,
        )

    def _create_company_a_worker(self):
        form = UserAccountCreateForm(
            user=self.owner_a,
            data={
                "first_name": "Worker A",
                "last_name": "Tenant",
                "email": "worker-a@example.com",
                "phone": "",
                "id_role": self.worker_role_a.pk,
                "status": "active",
                "identification": "",
                "position": "Technician",
                "password1": "Worker-A-Strong-2026!",
                "password2": "Worker-A-Strong-2026!",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_company_user_list_is_strictly_tenant_scoped(self):
        worker_a = self._create_company_a_worker()

        visible_ids = set(
            user_account_list_for_user(self.owner_a).values_list("id_user", flat=True)
        )

        self.assertIn(self.owner_a.id_user, visible_ids)
        self.assertIn(worker_a.id_user, visible_ids)
        self.assertNotIn(self.user_b.id_user, visible_ids)

    def test_company_role_from_another_tenant_cannot_be_assigned(self):
        form = UserAccountCreateForm(
            user=self.owner_a,
            data={
                "first_name": "Invalid Tenant",
                "last_name": "Role",
                "email": "invalid-role@example.com",
                "phone": "",
                "id_role": self.role_b.pk,
                "status": "active",
                "identification": "",
                "position": "",
                "password1": "Invalid-Role-Strong-2026!",
                "password2": "Invalid-Role-Strong-2026!",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("id_role", form.errors)

    def test_reaching_user_limit_blocks_new_active_user_not_existing_login(self):
        worker_a = self._create_company_a_worker()
        self.assertEqual(
            UserAccount.objects.filter(id_company=self.company_a, is_active=True).count(),
            2,
        )

        self.assertTrue(
            self.client.login(
                username=worker_a.email,
                password="Worker-A-Strong-2026!",
            )
        )

        extra_form = UserAccountCreateForm(
            user=self.owner_a,
            data={
                "first_name": "Third",
                "last_name": "User",
                "email": "third@example.com",
                "phone": "",
                "id_role": self.worker_role_a.pk,
                "status": "active",
                "identification": "",
                "position": "",
                "password1": "Third-User-Strong-2026!",
                "password2": "Third-User-Strong-2026!",
            },
        )
        self.assertFalse(extra_form.is_valid())
        self.assertIn("user limit", str(extra_form.non_field_errors()).lower())

    def test_active_user_without_modules_is_not_labeled_subscription_suspended(self):
        worker_a = self._create_company_a_worker()

        self.assertEqual(
            get_user_dashboard_url(worker_a),
            reverse("platform_core:no_permissions"),
        )

        self.client.force_login(worker_a)
        response = self.client.get(reverse("platform_core:account_suspended"))
        self.assertRedirects(
            response,
            reverse("platform_core:no_permissions"),
            fetch_redirect_response=False,
        )

        response = self.client.get(reverse("platform_core:no_permissions"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account Active")
        self.assertNotContains(response, "Company Workspace Suspended")

    def test_active_user_redirects_to_first_module_allowed_by_own_role(self):
        worker_a = self._create_company_a_worker()
        RolePermission.objects.create(
            id_role=self.worker_role_a,
            module="users",
            can_view=True,
        )

        self.assertEqual(
            get_user_dashboard_url(worker_a),
            f"/{self.company_a.slug}/users/",
        )
