from django.test import RequestFactory, TestCase

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.clients.views import ClientListView
from apps.companies.models import Company


class ClientListSearchTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserAccount.objects.create_superuser(
            email="client-search-admin@example.com",
            password="test-pass-123",
        )
        self.company = Company.objects.create(name="Client Search Company")
        self.target = Client.objects.create(
            id_company=self.company,
            name="María Search Target",
            dni="1799999999001",
            phone="0987654321",
            email="maria.target@example.com",
            address="Avenida de los Shyris 123",
        )
        Client.objects.create(
            id_company=self.company,
            name="Different Client",
            dni="1111111111",
            phone="0200000000",
            email="different@example.com",
            address="Another address",
        )

    def search(self, query):
        request = self.factory.get("/clients/", {"q": query})
        request.user = self.user
        view = ClientListView()
        view.request = request
        view.args = ()
        view.kwargs = {}
        return list(view.get_queryset())

    def test_unified_search_only_uses_code_name_and_dni(self):
        for term in (self.target.client_code, "María", "1799999999001"):
            with self.subTest(term=term):
                self.assertEqual(self.search(term), [self.target])

        for excluded_term in ("maria.target@example.com", "0987654321", "Shyris"):
            with self.subTest(excluded_term=excluded_term):
                self.assertEqual(self.search(excluded_term), [])
