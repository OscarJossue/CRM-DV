from datetime import timedelta

from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone
from unittest.mock import patch
from io import StringIO

from apps.accounts.forms import CRMLoginForm
from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company
from apps.companies.views import company_activate_view
from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code
from apps.core.permissions import user_has_module_permission
from apps.core.redirects import get_user_dashboard_url
from apps.platform_core.middleware import PlatformSubscriptionAccessMiddleware
from apps.platform_plans.models import PlatformPlan
from apps.platform_subscriptions.models import PlatformSubscription


class CompanyRuntimeAccessTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.company = Company.objects.create(
            name="Active Customer",
            status="active",
            plan="starter",
            user_limit=5,
        )
        self.role = Role.objects.create(
            id_company=self.company,
            name="Owner",
            status="active",
        )
        self.owner = UserAccount.objects.create_user(
            email="owner@example.com",
            password="admin12345",
            id_company=self.company,
            id_role=self.role,
            first_name="Owner",
            status="active",
            is_active=True,
            is_company_owner=True,
        )

    def test_active_company_user_can_login_without_subscription_record(self):
        form = CRMLoginForm(
            request=self.factory.post("/login/"),
            data={
                "username": self.owner.email,
                "password": "admin12345",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(get_user_runtime_access_code(self.owner), ACCESS_ALLOWED)

    def test_middleware_does_not_rewrite_active_company_for_expired_subscription(self):
        plan = PlatformPlan.objects.create(
            name="Starter Test",
            code="starter-test",
            price=10,
            billing_cycle="monthly",
            max_users=5,
            status="active",
        )
        PlatformSubscription.objects.create(
            id_company=self.company,
            id_plan=plan,
            status="expired",
            start_date=timezone.localdate() - timedelta(days=60),
            renewal_date=timezone.localdate() - timedelta(days=30),
        )

        request = self.factory.get(f"/{self.company.slug}/dashboard/")
        request.user = self.owner
        middleware = PlatformSubscriptionAccessMiddleware(lambda req: HttpResponse("ok"))

        response = middleware(request)
        self.company.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.company.status, "active")

    def test_company_owner_is_not_locked_out_by_empty_role_permissions(self):
        self.assertFalse(self.role.permissions.exists())
        self.assertTrue(user_has_module_permission(self.owner, "dashboard", "can_view"))
        self.assertEqual(
            get_user_dashboard_url(self.owner),
            f"/{self.company.slug}/dashboard/",
        )


    def test_platform_activation_without_subscription_remains_active(self):
        self.company.status = "inactive"
        self.company.save(update_fields=["status"])

        platform_user = UserAccount.objects.create_superuser(
            email="platform@example.com",
            password="admin12345",
            first_name="Platform",
        )

        request = self.factory.post(f"/companies/{self.company.pk}/activate/")
        request.user = platform_user

        with patch("apps.companies.views.messages.success"), patch(
            "apps.companies.views.log_platform_action"
        ):
            response = company_activate_view(request, self.company.pk)

        self.company.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.company.status, "active")


    def test_repair_company_login_command_repairs_owner_access(self):
        self.company.status = "inactive"
        self.company.save(update_fields=["status"])
        self.owner.is_active = False
        self.owner.status = "inactive"
        self.owner.save(update_fields=["is_active", "status"])

        output = StringIO()
        call_command(
            "repair_company_login",
            email=self.owner.email,
            stdout=output,
        )

        self.company.refresh_from_db()
        self.owner.refresh_from_db()
        self.role.refresh_from_db()

        self.assertTrue(self.owner.is_active)
        self.assertEqual(self.owner.status, "active")
        self.assertEqual(self.company.status, "active")
        self.assertGreater(self.role.permissions.count(), 0)
        self.assertIn("Runtime access: allowed", output.getvalue())

    def test_inactive_company_still_blocks_company_user(self):
        self.company.status = "inactive"
        self.company.save(update_fields=["status"])
        self.owner.refresh_from_db()

        form = CRMLoginForm(
            request=self.factory.post("/login/"),
            data={
                "username": self.owner.email,
                "password": "admin12345",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("inactive or suspended", str(form.non_field_errors()).lower())
