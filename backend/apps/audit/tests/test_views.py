from django.test import RequestFactory, TestCase

from apps.accounts.models import UserAccount
from apps.audit.context import reset_current_request, set_current_request
from apps.audit.models import SystemLog
from apps.clients.models import Client
from apps.companies.models import Company


class AutomaticHistorySignalTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Signal Company")
        self.user = UserAccount.objects.create_user(
            email="employee@example.com",
            password="StrongPassword123!",
            first_name="Employee",
            id_company=self.company,
        )
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.post(f"/{self.company.slug}/clients/create/")
        request.user = self.user
        request.current_company = self.company
        return request

    def test_create_update_delete_client_are_recorded(self):
        token = set_current_request(self._request())
        try:
            client = Client.objects.create(id_company=self.company, name="Signal Client")
            client.phone = "555-0101"
            client.save(update_fields=["phone", "updated_at"])
            client_id = client.pk
            client.delete()
        finally:
            reset_current_request(token)

        client_logs = SystemLog.objects.filter(
            id_company=self.company,
            object_type="Client",
            object_id=str(client_id),
        ).order_by("created_at", "id_log")

        self.assertEqual(
            list(client_logs.values_list("action_type", flat=True)),
            ["created", "updated", "deleted"],
        )
        self.assertTrue(all(item.actor_email == self.user.email for item in client_logs))
        self.assertIn("phone", client_logs[1].changes)
        self.assertEqual(client_logs[2].severity, "critical")

class HistoryRoutingTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Routing Company")
        self.user = UserAccount.objects.create_user(
            email="owner-routing@example.com",
            password="StrongPassword123!",
            first_name="Owner",
            id_company=self.company,
            is_company_owner=True,
        )
        self.client.force_login(self.user)

    def test_company_history_page_renders_without_horizontal_table_dependency(self):
        response = self.client.get(f"/{self.company.slug}/system-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "History")
        self.assertContains(response, "Automatic retention enabled")

    def test_legacy_user_activity_route_redirects_to_history(self):
        response = self.client.get(f"/{self.company.slug}/user-activities/dashboard/")
        self.assertRedirects(
            response,
            f"/{self.company.slug}/system-logs/",
            fetch_redirect_response=False,
        )
