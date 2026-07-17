from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase
from django.utils import translation


class CompanyUITranslationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_static_ui_translates_but_user_variable_stays_unchanged(self):
        request = self.factory.get("/acme/clients/")
        template = Template(
            '<h1>Clients</h1><p>{{ customer_name }}</p>'
            '<input placeholder="Search by name">'
        )

        with translation.override("es"):
            output = template.render(
                Context(
                    {
                        "request": request,
                        "customer_name": "Clients",
                    }
                )
            )

        self.assertIn("<h1>Clientes</h1>", output)
        self.assertIn("<p>Clients</p>", output)
        self.assertIn('placeholder="Buscar por nombre"', output)

    def test_platform_management_translates_with_platform_language(self):
        request = self.factory.get("/crm/companies/")
        template = Template("<h1>CRM Admin Dashboard</h1><p>Companies</p>")

        with translation.override("es"):
            output = template.render(Context({"request": request}))

        self.assertIn("<h1>Panel de administración del CRM</h1>", output)
        self.assertIn("<p>Empresas</p>", output)

    def test_inline_css_and_javascript_are_not_modified(self):
        request = self.factory.get("/acme/dashboard/")
        template = Template(
            '<style>.card { display: grid; color: red; }</style>'
            '<h1>Clients</h1>'
            '<script>const title = "Clients";</script>'
        )

        with translation.override("es"):
            output = template.render(Context({"request": request}))

        self.assertIn("display: grid", output)
        self.assertIn('const title = "Clients"', output)
        self.assertIn("<h1>Clientes</h1>", output)
