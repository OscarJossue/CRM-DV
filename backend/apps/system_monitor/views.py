from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from apps.companies.models import Company
from apps.core.platform_permissions import (
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)
from apps.platform_users.constants import (
    PLATFORM_MODULE_COMPANIES,
    PLATFORM_MODULE_SYSTEM_MONITOR,
)

from .services import get_system_monitor_data


class SystemMonitorView(LoginRequiredMixin, PlatformPermissionRequiredMixin, TemplateView):
    platform_module_name = PLATFORM_MODULE_SYSTEM_MONITOR
    platform_permission_required = PERMISSION_VIEW

    template_name = "system_monitor/status.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company_id = self.request.GET.get("company_id")
        monitor_data = get_system_monitor_data(
            self.request.user,
            company_id=company_id,
        )

        can_select_company = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_COMPANIES,
            PERMISSION_VIEW,
        )

        context["page_title"] = "System Monitor"
        context["monitor"] = monitor_data
        context["selected_company_id"] = str(
            monitor_data.get("selected_company_id") or ""
        )

        if can_select_company:
            context["companies"] = Company.objects.all().order_by("name")
        else:
            context["companies"] = []

        return context


class SystemMonitorAPIView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        if not user_can_platform_action(
            request.user,
            PLATFORM_MODULE_SYSTEM_MONITOR,
            PERMISSION_VIEW,
        ):
            return JsonResponse(
                {
                    "detail": "You do not have permission to access the system monitor.",
                    "code": "platform_permission_denied",
                },
                status=403,
            )

        company_id = request.GET.get("company_id")
        monitor_data = get_system_monitor_data(
            request.user,
            company_id=company_id,
        )

        return JsonResponse(monitor_data)