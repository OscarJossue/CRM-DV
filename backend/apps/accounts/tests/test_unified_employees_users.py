from django.test import TestCase
from django.utils import timezone

from apps.accounts.forms import UserAccountCreateForm, UserAccountUpdateForm
from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.serializers import UserAccountSerializer
from apps.accounts.views import get_role_module_choices_for_user
from apps.companies.models import Company
from apps.core.permissions import user_has_module_permission
from apps.employees.models import Employee


class UnifiedEmployeesUsersTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Unified Team",
            status="active",
            plan="starter",
            user_limit=10,
        )
        self.owner_role = Role.objects.create(
            id_company=self.company,
            name="Owner",
            status="active",
        )
        self.employee_role = Role.objects.create(
            id_company=self.company,
            name="Technician",
            status="active",
        )
        self.owner = UserAccount.objects.create_user(
            email="owner-unified@example.com",
            password="Owner-Strong-2026!",
            first_name="Owner",
            last_name="Unified",
            id_company=self.company,
            id_role=self.owner_role,
            status="active",
            is_active=True,
            is_company_owner=True,
        )

    def create_form_data(self, **overrides):
        data = {
            "first_name": "Maria",
            "last_name": "Lopez",
            "email": "maria.lopez@example.com",
            "phone": "+593999111222",
            "id_role": self.employee_role.pk,
            "status": "active",
            "identification": "1712345678",
            "position": "Field Supervisor",
            "password1": "Unique-Employee-2026!",
            "password2": "Unique-Employee-2026!",
        }
        data.update(overrides)
        return data

    def test_create_form_builds_one_user_and_one_employee_profile(self):
        form = UserAccountCreateForm(data=self.create_form_data(), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()
        profile = Employee.objects.get(id_user=user)

        self.assertEqual(user.id_company, self.company)
        self.assertEqual(user.id_role, self.employee_role)
        self.assertTrue(user.check_password("Unique-Employee-2026!"))
        self.assertEqual(profile.identification, "1712345678")
        self.assertEqual(profile.position, "Field Supervisor")
        self.assertEqual(profile.status, "active")
        self.assertEqual(profile.hire_date, user.created_at.date())

    def test_direct_user_creation_also_creates_compatibility_profile(self):
        user = UserAccount.objects.create_user(
            email="direct@example.com",
            password="Direct-Strong-2026!",
            first_name="Direct",
            last_name="User",
            id_company=self.company,
            id_role=self.employee_role,
            status="active",
            is_active=True,
        )

        profile = Employee.objects.get(id_user=user)
        self.assertEqual(profile.id_company, self.company)
        self.assertEqual(profile.status, "active")
        self.assertEqual(profile.hire_date, user.created_at.date())

    def test_update_form_syncs_profile_status_and_keeps_password_when_blank(self):
        create_form = UserAccountCreateForm(data=self.create_form_data(), user=self.owner)
        self.assertTrue(create_form.is_valid(), create_form.errors)
        user = create_form.save()
        old_password = user.password

        update_data = self.create_form_data(
            first_name="Mariana",
            email="mariana.lopez@example.com",
            identification="",
            position="Project Manager",
            status="inactive",
            password1="",
            password2="",
        )
        form = UserAccountUpdateForm(instance=user, data=update_data, user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        updated.refresh_from_db()
        updated.employee_profile.refresh_from_db()

        self.assertEqual(updated.first_name, "Mariana")
        self.assertEqual(updated.email, "mariana.lopez@example.com")
        self.assertEqual(updated.password, old_password)
        self.assertFalse(updated.is_active)
        self.assertEqual(updated.status, "inactive")
        self.assertIsNone(updated.employee_profile.identification)
        self.assertEqual(updated.employee_profile.position, "Project Manager")
        self.assertEqual(updated.employee_profile.status, "inactive")

    def test_partial_api_update_does_not_clear_employment_fields(self):
        form = UserAccountCreateForm(data=self.create_form_data(), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        class Request:
            pass

        request = Request()
        request.user = self.owner
        serializer = UserAccountSerializer(
            user,
            data={"phone": "+593222333444"},
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        user.employee_profile.refresh_from_db()
        self.assertEqual(user.employee_profile.identification, "1712345678")
        self.assertEqual(user.employee_profile.position, "Field Supervisor")

    def test_employee_permission_alias_uses_users_permission(self):
        RolePermission.objects.create(
            id_role=self.employee_role,
            module="users",
            can_view=True,
            can_edit=True,
        )
        user = UserAccount.objects.create_user(
            email="permission@example.com",
            password="Permission-Strong-2026!",
            first_name="Permission",
            id_company=self.company,
            id_role=self.employee_role,
            status="active",
            is_active=True,
        )

        self.assertTrue(user_has_module_permission(user, "users", "can_view"))
        self.assertTrue(user_has_module_permission(user, "employees", "can_view"))
        self.assertTrue(user_has_module_permission(user, "employees", "can_edit"))

    def test_role_matrix_contains_users_but_not_legacy_employees_module(self):
        choices = dict(get_role_module_choices_for_user(self.owner))
        self.assertIn("users", choices)
        self.assertNotIn("employees", choices)


    def test_unified_list_create_detail_and_edit_pages_render(self):
        form = UserAccountCreateForm(data=self.create_form_data(), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.client.force_login(self.owner)

        pages = (
            (f"/{self.company.slug}/users/", "Employees &amp; Users"),
            (f"/{self.company.slug}/users/create/", "Create Employee &amp; User"),
            (f"/{self.company.slug}/users/{user.pk}/", "Unified Profile"),
            (f"/{self.company.slug}/users/{user.pk}/edit/", "Edit Employee &amp; User"),
        )
        for url, expected in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)

    def test_legacy_employee_pages_redirect_to_unified_user_pages(self):
        form = UserAccountCreateForm(data=self.create_form_data(), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        profile = user.employee_profile

        self.client.force_login(self.owner)

        response = self.client.get(f"/{self.company.slug}/employees/")
        self.assertRedirects(
            response,
            f"/{self.company.slug}/users/",
            fetch_redirect_response=False,
        )

        response = self.client.get(f"/{self.company.slug}/employees/{profile.pk}/")
        self.assertRedirects(
            response,
            f"/{self.company.slug}/users/{user.pk}/",
            fetch_redirect_response=False,
        )
