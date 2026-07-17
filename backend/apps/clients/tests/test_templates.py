from django.template.loader import get_template
from django.test import SimpleTestCase


class ClientTemplateIntegrityTests(SimpleTestCase):
    def test_client_templates_compile(self):
        for template_name in [
            "clients/list.html",
            "clients/form.html",
            "clients/detail.html",
        ]:
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))
