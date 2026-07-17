import uuid
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.estimates.views import (
    build_estimate_action_urls,
    build_public_estimate_action_urls,
    reverse_estimate_url,
)


class EstimateRouteIntegrityTests(SimpleTestCase):
    company_slug = "peluche-roofing"

    def setUp(self):
        self.factory = RequestFactory()
        self.public_token = uuid.UUID("11111111-1111-4111-8111-111111111111")
        self.estimate = SimpleNamespace(
            id_estimate=123,
            id_project_id=456,
            public_token=self.public_token,
        )

    def namespace_kwargs(self, namespace):
        if namespace == "company_estimates":
            return {"company_slug": self.company_slug}
        return {}

    def build_request(self, namespace):
        url = reverse(
            f"{namespace}:estimate_list",
            kwargs=self.namespace_kwargs(namespace),
        )
        request = self.factory.get(url)
        request.resolver_match = resolve(url)
        return request

    def assert_all_named_routes_resolve(self, namespace):
        cases = {
            "estimate_list": {},
            "estimate_projects_for_client": {"id_client": 11},
            "public_estimate_preview": {"token": self.public_token},
            "public_estimate_approve": {"token": self.public_token},
            "public_estimate_reject": {"token": self.public_token},
            "estimate_create": {},
            "estimate_create_for_project": {"id_project": 22},
            "estimate_send": {"id_estimate": 33},
            "estimate_update": {"id_estimate": 33},
            "estimate_approve": {"id_estimate": 33},
            "estimate_reject": {"id_estimate": 33},
            "estimate_cancel": {"id_estimate": 33},
            "estimate_delete": {"id_estimate": 33},
            "estimate_project_create": {"id_estimate": 33},
            "estimate_project_update": {"id_estimate": 33},
            "estimate_pdf_style": {"id_estimate": 33},
            "estimate_pdf": {"id_estimate": 33},
            "estimate_detail": {"id_estimate": 33},
        }

        for route_name, route_kwargs in cases.items():
            kwargs = self.namespace_kwargs(namespace)
            kwargs.update(route_kwargs)
            url = reverse(f"{namespace}:{route_name}", kwargs=kwargs)
            match = resolve(url)
            self.assertEqual(match.namespace, namespace)
            self.assertEqual(match.url_name, route_name)

    def assert_action_urls(self, namespace):
        request = self.build_request(namespace)
        urls = build_estimate_action_urls(request, self.estimate)
        expected_routes = {
            "detail": "estimate_detail",
            "edit": "estimate_update",
            "pdf": "estimate_pdf",
            "pdf_style": "estimate_pdf_style",
            "send": "estimate_send",
            "approve": "estimate_approve",
            "reject": "estimate_reject",
            "cancel": "estimate_cancel",
            "delete": "estimate_delete",
            "project_create": "estimate_project_create",
            "project_update": "estimate_project_update",
        }

        for key, route_name in expected_routes.items():
            match = resolve(urls[key])
            self.assertEqual(match.namespace, namespace)
            self.assertEqual(match.url_name, route_name)
            self.assertEqual(match.kwargs["id_estimate"], self.estimate.id_estimate)

        project_match = resolve(urls["project_open"])
        expected_project_namespace = (
            "company_projects" if namespace == "company_estimates" else "projects"
        )
        self.assertEqual(project_match.namespace, expected_project_namespace)
        self.assertEqual(project_match.url_name, "project_detail")
        self.assertEqual(project_match.kwargs["id_project"], self.estimate.id_project_id)

        public_urls = build_public_estimate_action_urls(request, self.estimate)
        for key, route_name in (
            ("preview", "public_estimate_preview"),
            ("approve", "public_estimate_approve"),
            ("reject", "public_estimate_reject"),
        ):
            match = resolve(public_urls[key])
            self.assertEqual(match.namespace, namespace)
            self.assertEqual(match.url_name, route_name)
            self.assertEqual(match.kwargs["token"], self.estimate.public_token)

        create_url = reverse_estimate_url(request, "estimate_create")
        create_match = resolve(create_url)
        self.assertEqual(create_match.namespace, namespace)
        self.assertEqual(create_match.url_name, "estimate_create")

    def test_company_estimate_routes_keep_company_slug(self):
        self.assert_all_named_routes_resolve("company_estimates")
        self.assert_action_urls("company_estimates")

    def test_legacy_estimate_routes_remain_in_legacy_namespace(self):
        self.assert_all_named_routes_resolve("estimates")
        self.assert_action_urls("estimates")
