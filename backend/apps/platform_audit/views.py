from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from apps.core.platform_permissions import (
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
)
from apps.platform_users.constants import PLATFORM_MODULE_AUDIT

from .models import PlatformAuditLog


class PlatformAuditListView(LoginRequiredMixin, PlatformPermissionRequiredMixin, ListView):
    platform_module_name = PLATFORM_MODULE_AUDIT
    platform_permission_required = PERMISSION_VIEW

    model = PlatformAuditLog
    template_name = "platform_audit/list.html"
    context_object_name = "audit_logs"
    paginate_by = 30
    login_url = "/login/"

    def get_queryset(self):
        queryset = (
            PlatformAuditLog.objects.select_related(
                "actor_user",
                "id_company",
            )
            .all()
            .order_by("-created_at")
        )

        q = self.request.GET.get("q", "").strip()
        module_name = self.request.GET.get("module", "").strip()
        action = self.request.GET.get("action", "").strip()

        if q:
            queryset = queryset.filter(description__icontains=q)

        if module_name:
            queryset = queryset.filter(module_name=module_name)

        if action:
            queryset = queryset.filter(action=action)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Platform Audit"
        context["q"] = self.request.GET.get("q", "").strip()
        context["module_filter"] = self.request.GET.get("module", "").strip()
        context["action_filter"] = self.request.GET.get("action", "").strip()

        context["total_logs"] = PlatformAuditLog.objects.count()
        context["company_logs"] = PlatformAuditLog.objects.filter(module_name="companies").count()
        context["payment_logs"] = PlatformAuditLog.objects.filter(module_name="platform_payments").count()
        context["document_logs"] = PlatformAuditLog.objects.filter(module_name="platform_documents").count()

        context["modules"] = (
            PlatformAuditLog.objects.exclude(module_name="")
            .values_list("module_name", flat=True)
            .distinct()
            .order_by("module_name")
        )

        context["actions"] = (
            PlatformAuditLog.objects.exclude(action="")
            .values_list("action", flat=True)
            .distinct()
            .order_by("action")
        )

        return context


class PlatformAuditDetailView(LoginRequiredMixin, PlatformPermissionRequiredMixin, DetailView):
    platform_module_name = PLATFORM_MODULE_AUDIT
    platform_permission_required = PERMISSION_VIEW

    model = PlatformAuditLog
    template_name = "platform_audit/detail.html"
    context_object_name = "audit_log"
    pk_url_kwarg = "id_audit"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformAuditLog.objects.select_related(
            "actor_user",
            "id_company",
        )