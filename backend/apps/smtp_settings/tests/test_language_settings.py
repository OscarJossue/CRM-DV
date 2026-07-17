from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, RolePermission, UserAccount
from apps.companies.models import Company
from apps.platform_plans.models import PlatformPlan
from apps.platform_subscriptions.models import PlatformSubscription


class LanguageInsideEmailSettingsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Settings Language Company")
        plan = PlatformPlan.objects.create(
            name="Settings Language Plan",
            code="settings-language-plan",
            price=0,
            max_users=10,
        )
        PlatformSubscription.objects.create(
            id_company=self.company,
            id_plan=plan,
            status="active",
            start_date=timezone.localdate(),
            renewal_date=timezone.localdate() + timedelta(days=30),
        )

        self.owner_role = Role.objects.create(id_company=self.company, name="Owner")
        self.user_role = Role.objects.create(id_company=self.company, name="Staff")

        for role in (self.owner_role, self.user_role):
            RolePermission.objects.create(
                id_role=role,
                module="smtp_settings",
                can_view=True,
                can_create=True,
                can_edit=True,
            )

        self.owner = UserAccount.objects.create_user(
            email="owner-settings@example.com",
            password="strong-pass-123",
            first_name="Owner",
            id_company=self.company,
            id_role=self.owner_role,
            is_company_owner=True,
        )
        self.normal_user = UserAccount.objects.create_user(
            email="staff-settings@example.com",
            password="strong-pass-123",
            first_name="Staff",
            id_company=self.company,
            id_role=self.user_role,
            is_company_owner=False,
        )
        self.url = f"/{self.company.slug}/smtp-settings/"

    def test_owner_sees_language_inside_settings(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="language-settings"')
        self.assertContains(response, 'name="default_language"')

    def test_normal_user_does_not_see_language_selector(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="language-settings"')

    def test_owner_can_change_language_from_same_settings_route(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "settings_action": "save_language",
                "default_language": "es",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.default_language, "es")

    def test_normal_user_cannot_change_company_language(self):
        self.client.force_login(self.normal_user)
        response = self.client.post(
            self.url,
            {
                "settings_action": "save_language",
                "default_language": "es",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.default_language, "en")
