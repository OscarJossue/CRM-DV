from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_VIEW,
)

from .selectors import (
    get_financial_summary,
    get_payment_summary,
    get_project_summary,
)

from .services import (
    financial_summary_csv_response,
    financial_summary_pdf_response,
    payments_summary_csv_response,
    projects_summary_csv_response,
)


@method_decorator(never_cache, name="dispatch")
class ReportsHomeView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    template_name = "reports/list.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Reports"
        context["financial_summary"] = get_financial_summary(self.request.user)
        context["project_summary"] = get_project_summary(self.request.user)
        context["payment_summary"] = get_payment_summary(self.request.user)

        return context


@method_decorator(never_cache, name="dispatch")
class ReportsDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    template_name = "reports/detail.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Financial Summary"
        context["financial_summary"] = get_financial_summary(self.request.user)
        context["project_summary"] = get_project_summary(self.request.user)
        context["payment_summary"] = get_payment_summary(self.request.user)

        return context


@method_decorator(never_cache, name="dispatch")
class FinancialSummaryCSVView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return financial_summary_csv_response(request.user)


@method_decorator(never_cache, name="dispatch")
class ProjectsSummaryCSVView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return projects_summary_csv_response(request.user)


@method_decorator(never_cache, name="dispatch")
class PaymentsSummaryCSVView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return payments_summary_csv_response(request.user)


@method_decorator(never_cache, name="dispatch")
class FinancialSummaryPDFView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "reports"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return financial_summary_pdf_response(request.user)
