import csv
import json

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, StreamingHttpResponse
from django.urls import reverse
from django.views.generic import ListView, View
from rest_framework import viewsets
from rest_framework.permissions import BasePermission

from apps.core.permissions import HasModulePermission
from apps.core.template_permissions import ModulePermissionRequiredMixin, PERMISSION_VIEW

from .models import SystemLog
from .models.choices import ACTION_EXPORT, ACTION_TYPE_CHOICES, SEVERITY_CHOICES
from .selectors import (
    apply_system_log_filters,
    system_log_filter_options,
    system_log_list_for_user,
)
from .serializers import SystemLogSerializer
from .services import log_system_action




def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


class Echo:
    def write(self, value):
        return value


def _is_company_history_owner(user, company):
    """Allow only the account marked as the owner of the active company."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if not getattr(user, "is_company_owner", False):
        return False

    return bool(company and getattr(user, "id_company_id", None) == getattr(company, "pk", None))


def _humanize_key(value):
    return str(value or "").replace("_", " ").strip().title()


def _display_value(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _format_change_lines(changes):
    """Prepare compact, template-friendly lines without hiding audit data."""
    lines = []

    for field_name, payload in (changes or {}).items():
        label = _humanize_key(field_name)

        if isinstance(payload, dict) and ("old" in payload or "new" in payload):
            lines.append(
                {
                    "label": label,
                    "is_change": True,
                    "old": _display_value(payload.get("old")),
                    "new": _display_value(payload.get("new")),
                }
            )
            continue

        # Deleted-record snapshots and export filters are flattened so all
        # useful information remains visible directly in the principal list.
        if isinstance(payload, dict):
            if not payload:
                lines.append({"label": label, "is_change": False, "value": "—"})
                continue
            for nested_name, nested_value in payload.items():
                lines.append(
                    {
                        "label": f"{label} · {_humanize_key(nested_name)}",
                        "is_change": False,
                        "value": _display_value(nested_value),
                    }
                )
            continue

        lines.append(
            {
                "label": label,
                "is_change": False,
                "value": _display_value(payload),
            }
        )

    return lines


class HistoryScopeMixin:
    module_name = "system_logs"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get_company(self):
        return getattr(self.request, "current_company", None) or (
            None if self.request.user.is_superuser else getattr(self.request.user, "id_company", None)
        )

    def dispatch(self, request, *args, **kwargs):
        if not _is_company_history_owner(request.user, self.get_company()):
            return HttpResponseForbidden("Only the company owner can access the history.")
        return super().dispatch(request, *args, **kwargs)

    def get_base_queryset(self):
        return system_log_list_for_user(self.request.user, company=self.get_company())

    def history_url(self, name):
        company = self.get_company()
        if company and getattr(company, "slug", None):
            return reverse(
                f"company_audit:{name}",
                kwargs={"company_slug": company.slug},
            )
        return reverse(f"audit:{name}")


class SystemLogListView(LoginRequiredMixin, ModulePermissionRequiredMixin, HistoryScopeMixin, ListView):
    template_name = "audit/list.html"
    context_object_name = "system_logs"
    paginate_by = 40

    def get_queryset(self):
        return apply_system_log_filters(self.get_base_queryset(), self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_queryset = self.get_base_queryset()
        query_copy = self.request.GET.copy()
        query_copy.pop("page", None)

        for system_log in context.get("system_logs", []):
            system_log.change_lines = _format_change_lines(system_log.changes)

        context.update(
            {
                "page_title": "History",
                "page_subtitle": "Review the activity performed inside your company.",
                "history_filters": system_log_filter_options(base_queryset),
                "action_type_choices": ACTION_TYPE_CHOICES,
                "severity_choices": SEVERITY_CHOICES,
                "query_without_page": query_copy.urlencode(),
                "history_export_url": self.history_url("system_log_export"),
                "normal_retention_days": int(getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 3)),
                "critical_retention_days": int(getattr(settings, "AUDIT_CRITICAL_RETENTION_DAYS", 7)),
            }
        )
        return context


class SystemLogExportView(LoginRequiredMixin, ModulePermissionRequiredMixin, HistoryScopeMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = apply_system_log_filters(self.get_base_queryset(), request.GET)
        last_existing_id = queryset.order_by("-id_log").values_list("id_log", flat=True).first()
        if last_existing_id is not None:
            queryset = queryset.filter(id_log__lte=last_existing_id)
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        def rows():
            yield writer.writerow(
                [
                    "date",
                    "company",
                    "user",
                    "email",
                    "module",
                    "action_type",
                    "severity",
                    "record_type",
                    "record_id",
                    "record",
                    "ip",
                    "changes",
                ]
            )
            for item in queryset.iterator(chunk_size=2000):
                yield writer.writerow(
                    [
                        item.created_at.isoformat(),
                        item.id_company.name,
                        _csv_safe(item.actor_name),
                        _csv_safe(item.actor_email),
                        _csv_safe(item.module),
                        item.action_type,
                        item.severity,
                        item.object_type,
                        item.object_id,
                        _csv_safe(item.object_label),
                        _csv_safe(item.ip),
                        _csv_safe(json.dumps(item.changes, ensure_ascii=False, default=str)),
                    ]
                )

        company = self.get_company()
        log_system_action(
            user=request.user,
            company=company,
            module="system_logs",
            action="audit.systemlog:export",
            action_type=ACTION_EXPORT,
            request=request,
            object_type="History",
            object_label="CSV export",
            changes={"filters": {key: value for key, value in request.GET.items()}},
        )

        response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="crm-history.csv"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "no-referrer"
        return response


class IsCompanyHistoryOwner(BasePermission):
    """DRF equivalent of the owner-only history rule."""

    def has_permission(self, request, view):
        company = getattr(request, "current_company", None)
        if company is None:
            company = getattr(request.user, "id_company", None)
        return _is_company_history_owner(request.user, company)


class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    module_name = "system_logs"
    queryset = SystemLog.objects.select_related("id_company", "id_user").all()
    serializer_class = SystemLogSerializer
    permission_classes = [HasModulePermission, IsCompanyHistoryOwner]

    def get_queryset(self):
        company = getattr(self.request, "current_company", None)
        return apply_system_log_filters(
            system_log_list_for_user(self.request.user, company=company),
            self.request.query_params,
        )
