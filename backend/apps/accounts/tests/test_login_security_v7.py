from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.forms import CRMLoginForm
from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company


@override_settings(LOGIN_MAX_FAILURES=2, LOGIN_MAX_FAILURES_PER_IP=20, LOGIN_FAILURE_WINDOW_SECONDS=300)
class LoginSecurityV7Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name="Active Tenant", status="active")
        self.role = Role.objects.create(id_company=self.company, name="Owner")
        self.user = UserAccount.objects.create_user(
            email="tenant@example.com",
            password="admin12345",
            first_name="Tenant",
            id_company=self.company,
            id_role=self.role,
            status="active",
            is_active=True,
            is_company_owner=True,
        )
        self.request = RequestFactory().post("/login/", REMOTE_ADDR="203.0.113.9")

    def login_form(self, password):
        return CRMLoginForm(
            request=self.request,
            data={"username": "tenant@example.com", "password": password},
        )

    def test_repeated_failures_are_throttled_without_exposing_password(self):
        self.assertFalse(self.login_form("bad-one").is_valid())
        self.assertFalse(self.login_form("bad-two").is_valid())
        blocked = self.login_form("admin12345")
        self.assertFalse(blocked.is_valid())
        self.assertIn("Too many unsuccessful", str(blocked.non_field_errors()))

    def test_success_clears_previous_failure_counter(self):
        self.assertFalse(self.login_form("bad-one").is_valid())
        self.assertTrue(self.login_form("admin12345").is_valid())
        self.assertFalse(self.login_form("bad-again").is_valid())
        self.assertTrue(self.login_form("admin12345").is_valid())


class LoginHtmlIntegrityTests(TestCase):
    def test_spanish_login_preserves_machine_html_attributes(self):
        response = self.client.get("/login/?language=es")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="password"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'type="contraseña"')
        self.assertNotContains(response, 'type="correo electrónico"')
        self.assertContains(response, 'placeholder="Contraseña"')
        self.assertContains(response, 'class="nj-language-button is-active"')
        self.assertNotContains(response, 'class="nj-language-button es-activo"')


class DemoSeedProductionSafetyTests(TestCase):
    @override_settings(DEBUG=False)
    def test_demo_seed_is_blocked_in_production_by_default(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", verbosity=0)
