from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserAccount


class PlatformLanguagePreferenceTests(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="platform-language@example.com",
            password="StrongPass123!",
        )

    def test_anonymous_language_switch_translates_login_and_sets_cookie(self):
        response = self.client.post(
            reverse("language_switch"),
            {"language": "es", "next": reverse("login")},
        )

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value,
            "es",
        )

        login_response = self.client.get(reverse("login"))
        self.assertContains(login_response, "Bienvenido.")
        self.assertContains(login_response, "Inicio de sesión")
        self.assertEqual(login_response["Content-Language"], "es")

    def test_platform_language_page_updates_personal_preference(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("platform_languages:settings"),
            {
                "language": "es",
                "next": reverse("platform_languages:settings"),
            },
        )

        self.assertRedirects(
            response,
            reverse("platform_languages:settings"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "es")
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value,
            "es",
        )

        page = self.client.get(reverse("platform_languages:settings"))
        self.assertContains(page, "Idioma personal de la plataforma")
        self.assertContains(page, "Guardar idioma")
        self.assertEqual(page["Content-Language"], "es")

    def test_platform_dashboard_uses_saved_personal_language(self):
        self.user.preferred_language = "es"
        self.user.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("platform_core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "es")
        self.assertContains(response, "Panel de administración del CRM")
        self.assertContains(response, "Empresas activas")

    def test_main_platform_sections_render_in_saved_spanish(self):
        self.user.preferred_language = "es"
        self.user.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)

        route_names = [
            "platform_core:dashboard",
            "companies:company_list",
            "platform_plans:list",
            "platform_subscriptions:list",
            "platform_documents:list",
            "platform_payments:list",
            "platform_calendar:list",
            "platform_notifications:list",
            "platform_email:list",
            "platform_audit:list",
            "platform_users:user_list",
            "dashboard_metrics:resources_dashboard",
            "system_monitor:status",
            "platform_languages:settings",
        ]

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Language"], "es")

    def test_platform_create_forms_render_in_saved_spanish(self):
        self.user.preferred_language = "es"
        self.user.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)

        route_names = [
            "companies:company_onboarding",
            "companies:company_create",
            "platform_plans:create",
            "platform_subscriptions:create",
            "platform_documents:create",
            "platform_payments:create",
            "platform_calendar:create",
            "platform_email:compose",
            "platform_users:user_create",
        ]

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Language"], "es")
