from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.forms import CRMLoginForm, CRMPasswordResetForm
from apps.accounts.middleware import ActiveUserRequiredMiddleware
from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company


class SuperAdminCompanyStatusBypassTests(TestCase):
    password = "admin12345"

    def setUp(self):
        self.factory = RequestFactory()
        self.company = Company.objects.create(
            name="Suspended Tenant",
            plan="internal",
            status="inactive",
            user_limit=20,
        )
        self.role = Role.objects.create(
            id_company=self.company,
            name="Platform Administrator",
            status="active",
        )

    def create_user(self, email, *, is_staff=False, is_superuser=False, status="active"):
        user_kwargs = {
            "email": email,
            "password": self.password,
            "first_name": "Test",
            "status": status,
            "is_active": True,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
        }
        if not (is_staff or is_superuser):
            user_kwargs.update(id_company=self.company, id_role=self.role)
        return UserAccount.objects.create_user(**user_kwargs)

    def login_form(self, email):
        request = self.factory.post("/login/")
        request.user = AnonymousUser()
        return CRMLoginForm(
            request=request,
            data={"username": email, "password": self.password},
        )

    def test_superuser_can_login_without_tenant_company(self):
        user = self.create_user(
            "root@example.com",
            is_staff=True,
            is_superuser=True,
        )

        form = self.login_form(user.email)

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.get_user(), user)

    def test_platform_staff_can_login_without_tenant_company(self):
        user = self.create_user("staff@example.com", is_staff=True)

        form = self.login_form(user.email)

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.get_user(), user)

    def test_company_user_remains_blocked_when_company_is_inactive(self):
        user = self.create_user("tenant@example.com")

        form = self.login_form(user.email)

        self.assertFalse(form.is_valid())
        self.assertIn("inactive_company", form.errors.as_data()["__all__"][0].code)

    def test_superuser_is_still_blocked_when_own_user_status_is_inactive(self):
        user = self.create_user(
            "disabled-root@example.com",
            is_staff=True,
            is_superuser=True,
            status="inactive",
        )

        form = self.login_form(user.email)

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["__all__"][0].code, "inactive")

    def test_password_reset_includes_superuser_without_tenant_company(self):
        user = self.create_user(
            "reset-root@example.com",
            is_staff=True,
            is_superuser=True,
        )
        form = CRMPasswordResetForm(data={"email": user.email})

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(list(form.get_users(user.email)), [user])

    def test_active_user_middleware_does_not_logout_superuser_without_tenant_company(self):
        user = self.create_user(
            "middleware-root@example.com",
            is_staff=True,
            is_superuser=True,
        )
        request = self.factory.get("/platform/")
        request.user = user
        middleware = ActiveUserRequiredMiddleware(lambda current_request: HttpResponse("ok"))

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
