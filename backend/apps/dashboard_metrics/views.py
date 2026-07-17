from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse

from apps.companies.models import Company

from .services import get_dashboard_resource_metrics


class ResourceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard_metrics/resources.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company_id = self.request.GET.get("company_id")
        metrics = get_dashboard_resource_metrics(self.request.user, company_id=company_id)

        context["page_title"] = "Resources Dashboard"
        context["metrics"] = metrics
        context["is_global"] = metrics.get("is_global")
        context["company_name"] = metrics.get("company_name")
        context["selected_company_id"] = str(company_id or "")

        if self.request.user.is_superuser:
            context["companies"] = Company.objects.all().order_by("name")
        else:
            context["companies"] = []

        return context


class ResourceMetricsAPIView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        company_id = request.GET.get("company_id")
        metrics = get_dashboard_resource_metrics(request.user, company_id=company_id)

        return JsonResponse(metrics)