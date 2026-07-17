from django.test import RequestFactory, TestCase

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.opportunities.models import Lead
from apps.opportunities.views import LeadListView


class OpportunityListSearchTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserAccount.objects.create_superuser(
            email="opportunity-search-admin@example.com",
            password="test-pass-123",
        )
        self.company = Company.objects.create(name="Opportunity Search Company")
        self.client_record = Client.objects.create(
            id_company=self.company,
            name="Carlos Opportunity Target",
            dni="1717171717001",
            phone="0991112233",
            email="carlos.target@example.com",
            address="Quito",
        )
        self.target = Lead.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            id_assigned_user=self.user,
            status="qualified",
            source="website",
            approximate_value="2500.00",
        )
        other_client = Client.objects.create(
            id_company=self.company,
            name="Different Opportunity Client",
            dni="2222222222",
            phone="0222222222",
            email="different.opportunity@example.com",
        )
        Lead.objects.create(
            id_company=self.company,
            id_client=other_client,
            id_assigned_user=self.user,
            status="new",
            source="phone",
            approximate_value="100.00",
        )

    def search(self, query, **filters):
        params = {"q": query, **filters}
        request = self.factory.get("/opportunities/", params)
        request.user = self.user
        view = LeadListView()
        view.request = request
        view.args = ()
        view.kwargs = {}
        return list(view.get_queryset())

    def test_unified_search_finds_opportunity_and_client_identity_fields(self):
        identity_terms = [
            self.target.opportunity_code,
            self.client_record.client_code,
            "Carlos",
            "1717171717001",
        ]
        for term in identity_terms:
            with self.subTest(term=term):
                self.assertEqual(self.search(term), [self.target])

        for excluded_term in ("carlos.target@example.com", "0991112233"):
            with self.subTest(excluded_term=excluded_term):
                self.assertEqual(self.search(excluded_term), [])

    def test_status_cards_filter_and_legacy_source_parameter_is_ignored(self):
        self.assertEqual(
            self.search("Carlos", status="qualified", source="phone"),
            [self.target],
        )
        self.assertEqual(self.search("Carlos", status="new"), [])


class OpportunityInlineStatusUpdateTests(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_superuser(
            email="opportunity-status-admin@example.com",
            password="test-pass-123",
        )
        self.company = Company.objects.create(name="Opportunity Status Company")
        self.client_record = Client.objects.create(
            id_company=self.company,
            name="Inline Status Client",
            dni="1799999999001",
        )
        self.opportunity = Lead.objects.create(
            id_company=self.company,
            id_client=self.client_record,
            id_assigned_user=self.user,
            status="new",
            approximate_value="900.00",
        )
        self.client.force_login(self.user)

    def test_inline_status_endpoint_updates_the_persisted_opportunity(self):
        response = self.client.post(
            f"/opportunities/{self.opportunity.id_lead}/status/",
            {"status": "qualified"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "qualified")
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, "qualified")

    def test_converted_status_cannot_be_assigned_without_project_conversion(self):
        response = self.client.post(
            f"/opportunities/{self.opportunity.id_lead}/status/",
            {"status": "converted"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.opportunity.refresh_from_db()
        self.assertEqual(self.opportunity.status, "new")
