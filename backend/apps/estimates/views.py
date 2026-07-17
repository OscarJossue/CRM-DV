from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_GET, require_POST
from django.views import View
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)
from apps.inspections.models import InspectionAssignment
from apps.projects.forms import ProjectForm
from apps.projects.models import Project
from apps.projects.models.choices import PROJECT_STATUS_PENDING

from .forms import EstimateForm, EstimateItemFormSet, EstimateSendEmailForm
from .models import Estimate
from .models.choices import (
    ESTIMATE_EDIT_ALLOWED_STATUSES,
    ESTIMATE_SEND_ALLOWED_STATUSES,
    ESTIMATE_STATUS_APPROVED,
    ESTIMATE_STATUS_CANCELLED,
    ESTIMATE_STATUS_CONVERTED,
    ESTIMATE_STATUS_DRAFT,
    ESTIMATE_STATUS_EXPIRED,
    ESTIMATE_STATUS_PENDING,
    ESTIMATE_STATUS_PENDING_SEND,
    ESTIMATE_STATUS_REJECTED,
    ESTIMATE_STATUS_SENT,
    ESTIMATE_STATUS_VIEWED,
    ESTIMATE_STATUS_CHOICES,
)
from .permissions import user_can_access_estimate
from .selectors import estimate_list_for_user
from .serializers import EstimateSerializer
from .services import (
    EstimatePublicFlowError,
    approve_estimate_publicly,
    can_customer_decide_estimate,
    estimate_approve,
    estimate_cancel,
    estimate_pdf_response,
    estimate_reject,
    get_public_estimate_by_token,
    mark_estimate_as_viewed_publicly,
    recalculate_estimate,
    refresh_public_estimate_token,
    reject_estimate_publicly,
    reopen_rejected_estimate_after_edit,
    send_estimate_to_email,
)


ESTIMATE_RESEND_ALLOWED_STATUSES = [
    ESTIMATE_STATUS_SENT,
    ESTIMATE_STATUS_VIEWED,
    ESTIMATE_STATUS_REJECTED,
]

ESTIMATE_LOCKED_STATUSES = [
    ESTIMATE_STATUS_APPROVED,
    ESTIMATE_STATUS_CONVERTED,
    ESTIMATE_STATUS_CANCELLED,
]

ESTIMATE_CANCEL_ALLOWED_STATUSES = [
    ESTIMATE_STATUS_DRAFT,
    ESTIMATE_STATUS_PENDING,
    ESTIMATE_STATUS_PENDING_SEND,
    ESTIMATE_STATUS_SENT,
    ESTIMATE_STATUS_VIEWED,
    ESTIMATE_STATUS_REJECTED,
    ESTIMATE_STATUS_EXPIRED,
]


ESTIMATE_DASHBOARD_STATUS_GROUPS = [
    {"key": ESTIMATE_STATUS_DRAFT, "label": "Draft", "statuses": [ESTIMATE_STATUS_DRAFT]},
    {"key": ESTIMATE_STATUS_PENDING_SEND, "label": "Pending Send", "statuses": [ESTIMATE_STATUS_PENDING, ESTIMATE_STATUS_PENDING_SEND]},
    {"key": ESTIMATE_STATUS_SENT, "label": "Sent", "statuses": [ESTIMATE_STATUS_SENT, ESTIMATE_STATUS_VIEWED]},
    {"key": ESTIMATE_STATUS_APPROVED, "label": "Approved", "statuses": [ESTIMATE_STATUS_APPROVED]},
    {"key": ESTIMATE_STATUS_REJECTED, "label": "Rejected", "statuses": [ESTIMATE_STATUS_REJECTED]},
    {"key": ESTIMATE_STATUS_EXPIRED, "label": "Expired", "statuses": [ESTIMATE_STATUS_EXPIRED]},
    {"key": ESTIMATE_STATUS_CONVERTED, "label": "Converted", "statuses": [ESTIMATE_STATUS_CONVERTED]},
    {"key": ESTIMATE_STATUS_CANCELLED, "label": "Cancelled", "statuses": [ESTIMATE_STATUS_CANCELLED]},
]

ESTIMATE_DASHBOARD_STATUS_KEYS = {
    group["key"] for group in ESTIMATE_DASHBOARD_STATUS_GROUPS
}


def get_estimate_status_group(status_key):
    for group in ESTIMATE_DASHBOARD_STATUS_GROUPS:
        if group["key"] == status_key:
            return group
    return None


def project_queryset_for_user(user):
    queryset = Project.objects.select_related(
        "id_company",
        "id_client",
    ).all()

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def get_request_company_slug(request, company_slug=None):
    """Return the company slug attached to the active request, when available."""
    if company_slug:
        return company_slug

    resolver_match = getattr(request, "resolver_match", None)
    resolver_kwargs = getattr(resolver_match, "kwargs", {}) or {}
    resolver_company_slug = resolver_kwargs.get("company_slug")

    if resolver_company_slug:
        return resolver_company_slug

    current_company = getattr(request, "current_company", None)

    if current_company and getattr(current_company, "slug", None):
        return current_company.slug

    user_company = getattr(getattr(request, "user", None), "id_company", None)

    if user_company and getattr(user_company, "slug", None):
        return user_company.slug

    return None


def get_active_estimate_namespace(request, company_slug=None):
    """Keep links inside the same tenant/legacy namespace as the current page."""
    resolver_match = getattr(request, "resolver_match", None)
    namespace = getattr(resolver_match, "namespace", "") or ""

    if namespace == "company_estimates":
        return namespace, get_request_company_slug(request, company_slug)

    if namespace == "estimates":
        return namespace, None

    active_company_slug = get_request_company_slug(request, company_slug)

    if active_company_slug:
        return "company_estimates", active_company_slug

    return "estimates", None


def reverse_estimate_url(request, view_name, company_slug=None, kwargs=None):
    """Reverse an estimate route without ever losing or inventing tenant context."""
    kwargs = dict(kwargs or {})
    namespace, active_company_slug = get_active_estimate_namespace(
        request,
        company_slug,
    )

    if namespace == "company_estimates":
        if not active_company_slug:
            raise ValueError(
                "A company slug is required to reverse company estimate routes."
            )
        kwargs["company_slug"] = active_company_slug

    return reverse(f"{namespace}:{view_name}", kwargs=kwargs)


def redirect_estimate_url(request, view_name, company_slug=None, kwargs=None):
    return redirect(
        reverse_estimate_url(
            request=request,
            view_name=view_name,
            company_slug=company_slug,
            kwargs=kwargs,
        )
    )


def build_public_estimate_url(request, estimate, company_slug=None):
    base_url = getattr(settings, "CRM_PUBLIC_BASE_URL", "").rstrip("/")
    path = reverse_estimate_url(
        request,
        "public_estimate_preview",
        company_slug=company_slug,
        kwargs={"token": estimate.public_token},
    )

    if base_url:
        return f"{base_url}{path}"

    return request.build_absolute_uri(path)


def get_public_estimate_context(
    request,
    estimate,
    company_slug=None,
    page_title="Estimate Review",
    **extra_context,
):
    public_urls = build_public_estimate_action_urls(
        request,
        estimate,
        company_slug=company_slug,
    )
    context = {
        "estimate": estimate,
        "page_title": page_title,
        "can_customer_decide": can_customer_decide_estimate(estimate),
        "public_preview_url": public_urls["preview"],
        "public_approve_url": public_urls["approve"],
        "public_reject_url": public_urls["reject"],
    }
    context.update(extra_context)
    return context


def reverse_project_url(request, view_name, company_slug=None, kwargs=None):
    """Reverse a project route using the same tenant context as estimates."""
    kwargs = dict(kwargs or {})
    estimate_namespace, active_company_slug = get_active_estimate_namespace(
        request,
        company_slug,
    )

    if estimate_namespace == "company_estimates":
        if not active_company_slug:
            raise ValueError(
                "A company slug is required to reverse company project routes."
            )
        kwargs["company_slug"] = active_company_slug
        return reverse(f"company_projects:{view_name}", kwargs=kwargs)

    return reverse(f"projects:{view_name}", kwargs=kwargs)


def redirect_project_url(request, view_name, company_slug=None, kwargs=None):
    return redirect(
        reverse_project_url(
            request=request,
            view_name=view_name,
            company_slug=company_slug,
            kwargs=kwargs,
        )
    )


def reverse_inspection_assignment_url(request, assignment, company_slug=None):
    estimate_namespace, active_company_slug = get_active_estimate_namespace(
        request, company_slug
    )
    kwargs = {"id_assignment": assignment.id_assignment}
    if estimate_namespace == "company_estimates":
        kwargs["company_slug"] = active_company_slug
        return reverse("company_inspections:inspection_detail", kwargs=kwargs)
    return reverse("inspections:inspection_detail", kwargs=kwargs)


def build_estimate_action_urls(request, estimate, company_slug=None):
    """Return every internal action URL used by the estimate UI."""
    estimate_kwargs = {"id_estimate": estimate.id_estimate}
    urls = {
        "detail": reverse_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "edit": reverse_estimate_url(
            request,
            "estimate_update",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "pdf": reverse_estimate_url(
            request,
            "estimate_pdf",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "pdf_style": reverse_estimate_url(
            request,
            "estimate_pdf_style",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "send": reverse_estimate_url(
            request,
            "estimate_send",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "approve": reverse_estimate_url(
            request,
            "estimate_approve",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "reject": reverse_estimate_url(
            request,
            "estimate_reject",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "cancel": reverse_estimate_url(
            request,
            "estimate_cancel",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "delete": reverse_estimate_url(
            request,
            "estimate_delete",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "project_create": reverse_estimate_url(
            request,
            "estimate_project_create",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
        "project_update": reverse_estimate_url(
            request,
            "estimate_project_update",
            company_slug=company_slug,
            kwargs=estimate_kwargs,
        ),
    }

    urls["project_open"] = None
    if estimate.id_project_id:
        urls["project_open"] = reverse_project_url(
            request,
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": estimate.id_project_id},
        )

    urls["inspection_open"] = None
    inspection_assignment_id = getattr(estimate, "id_inspection_assignment_id", None)
    inspection_assignment = getattr(estimate, "id_inspection_assignment", None)
    if inspection_assignment_id and inspection_assignment:
        urls["inspection_open"] = reverse_inspection_assignment_url(
            request,
            inspection_assignment,
            company_slug=company_slug,
        )

    return urls


def build_public_estimate_action_urls(request, estimate, company_slug=None):
    """Return explicit public preview/decision routes for a customer token."""
    token_kwargs = {"token": estimate.public_token}
    return {
        "preview": reverse_estimate_url(
            request,
            "public_estimate_preview",
            company_slug=company_slug,
            kwargs=token_kwargs,
        ),
        "approve": reverse_estimate_url(
            request,
            "public_estimate_approve",
            company_slug=company_slug,
            kwargs=token_kwargs,
        ),
        "reject": reverse_estimate_url(
            request,
            "public_estimate_reject",
            company_slug=company_slug,
            kwargs=token_kwargs,
        ),
    }


def get_estimate_project_initial(estimate):
    client = estimate.id_client

    client_address = (
        getattr(client, "address", "")
        or getattr(client, "client_address", "")
        or getattr(client, "billing_address", "")
        or ""
    )

    project_name = (
        estimate.project_name
        or estimate.description
        or f"{estimate.estimate_number or 'Estimate'} - {client.name}"
    )

    description = estimate.notes or estimate.description or ""

    if not description:
        item_descriptions = [
            item.description
            for item in estimate.items.all()
            if getattr(item, "description", None)
        ]
        description = "\n".join(item_descriptions)

    return {
        "id_client": client,
        "name": str(project_name).strip()[:255],
        "project_address": estimate.project_address or client_address,
        "description": description,
        "status": PROJECT_STATUS_PENDING,
        "contract_amount": estimate.total or 0,
        "start_date": timezone.localdate(),
        "end_date": None,
    }


def normalize_project_text(value):
    return (value or "").strip()


def normalize_project_money(value):
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def get_estimate_project_sync_changes(estimate):
    """Return the linked project fields that are different from estimate data."""
    project = getattr(estimate, "id_project", None)

    if not project:
        return []

    changes = []

    estimate_project_name = normalize_project_text(getattr(estimate, "project_name", ""))
    project_name = normalize_project_text(getattr(project, "name", ""))

    if estimate_project_name and estimate_project_name != project_name:
        changes.append(
            {
                "field": "Project Name",
                "from": project_name or "-",
                "to": estimate_project_name,
            }
        )

    estimate_project_address = normalize_project_text(getattr(estimate, "project_address", ""))
    project_address = normalize_project_text(getattr(project, "project_address", ""))

    if estimate_project_address and estimate_project_address != project_address:
        changes.append(
            {
                "field": "Project Address",
                "from": project_address or "-",
                "to": estimate_project_address,
            }
        )

    estimate_description = normalize_project_text(getattr(estimate, "description", ""))
    project_description = normalize_project_text(getattr(project, "description", ""))

    if estimate_description and estimate_description != project_description:
        changes.append(
            {
                "field": "Description",
                "from": project_description or "-",
                "to": estimate_description,
            }
        )

    estimate_total = normalize_project_money(getattr(estimate, "total", Decimal("0.00")))
    project_contract_amount = normalize_project_money(getattr(project, "contract_amount", Decimal("0.00")))

    if estimate_total != project_contract_amount:
        changes.append(
            {
                "field": "Contract Amount",
                "from": f"${project_contract_amount}",
                "to": f"${estimate_total}",
            }
        )

    return changes


def update_project_from_estimate(estimate, user=None):
    """Update only the linked project fields that changed in the estimate."""
    project = getattr(estimate, "id_project", None)

    if not project:
        return []

    updated_fields = []
    updated_labels = []

    estimate_project_name = normalize_project_text(getattr(estimate, "project_name", ""))

    if estimate_project_name and estimate_project_name != normalize_project_text(project.name):
        project.name = estimate_project_name
        updated_fields.append("name")
        updated_labels.append("Project Name")

    estimate_project_address = normalize_project_text(getattr(estimate, "project_address", ""))

    if estimate_project_address and estimate_project_address != normalize_project_text(project.project_address):
        project.project_address = estimate_project_address
        updated_fields.append("project_address")
        updated_labels.append("Project Address")

    estimate_description = normalize_project_text(getattr(estimate, "description", ""))

    if estimate_description and estimate_description != normalize_project_text(project.description):
        project.description = estimate_description
        updated_fields.append("description")
        updated_labels.append("Description")

    estimate_total = normalize_project_money(getattr(estimate, "total", Decimal("0.00")))
    project_contract_amount = normalize_project_money(getattr(project, "contract_amount", Decimal("0.00")))

    if estimate_total != project_contract_amount:
        project.contract_amount = estimate_total
        updated_fields.append("contract_amount")
        updated_labels.append("Contract Amount")

    if updated_fields:
        if user and getattr(user, "is_authenticated", False):
            project.updated_by = user
            updated_fields.append("updated_by")

        if hasattr(project, "updated_at"):
            project.updated_at = timezone.now()
            updated_fields.append("updated_at")

        project.save(update_fields=list(dict.fromkeys(updated_fields)))

    return updated_labels


def get_requested_estimate_status(request, current_status=None):
    save_mode = request.POST.get("save_mode")

    if current_status in [
        ESTIMATE_STATUS_PENDING,
        ESTIMATE_STATUS_PENDING_SEND,
    ]:
        return ESTIMATE_STATUS_PENDING_SEND

    if save_mode == "draft":
        return ESTIMATE_STATUS_DRAFT

    return ESTIMATE_STATUS_PENDING_SEND


@require_GET
def estimate_projects_for_client_view(request, id_client, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_VIEW,
    )

    if permission_response:
        return permission_response

    projects = project_queryset_for_user(request.user).filter(
        id_client_id=id_client,
    ).order_by("-created_at")

    data = []

    for project in projects:
        code = project.project_code or f"P_{project.id_project:05d}"
        name = project.name or ""
        label = f"{code} - {name}" if name else code

        data.append(
            {
                "id": project.id_project,
                "label": label,
                "name": name,
                "project_address": project.project_address or "",
                "description": project.description or "",
                "contract_amount": str(project.contract_amount or "0.00"),
            }
        )

    return JsonResponse({"projects": data})


class EstimateListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "estimates"
    permission_required = PERMISSION_VIEW
    template_name = "estimates/list.html"
    context_object_name = "estimates"
    paginate_by = 20
    login_url = "/login/"

    def get_base_queryset(self):
        return estimate_list_for_user(self.request.user)

    def get_queryset(self):
        queryset = self.get_base_queryset()

        status_filter = (self.request.GET.get("status") or "").strip()
        search_query = (self.request.GET.get("q") or "").strip()

        status_group = get_estimate_status_group(status_filter)

        if status_group:
            queryset = queryset.filter(status__in=status_group["statuses"])

        if search_query:
            queryset = queryset.filter(
                Q(id_client__name__icontains=search_query)
                | Q(client_billing_name__icontains=search_query)
                | Q(project_name__icontains=search_query)
                | Q(estimate_number__icontains=search_query)
            )

        return queryset

    def get_status_color_map(self):
        return {
            ESTIMATE_STATUS_DRAFT: "#64748b",
            ESTIMATE_STATUS_PENDING_SEND: "#f59e0b",
            ESTIMATE_STATUS_SENT: "#2563eb",
            ESTIMATE_STATUS_APPROVED: "#16a34a",
            ESTIMATE_STATUS_REJECTED: "#dc2626",
            ESTIMATE_STATUS_EXPIRED: "#b91c1c",
            ESTIMATE_STATUS_CONVERTED: "#7c3aed",
            ESTIMATE_STATUS_CANCELLED: "#6b7280",
        }

    def build_status_query_string(self, status=None):
        params = {}
        search_query = (self.request.GET.get("q") or "").strip()

        if search_query:
            params["q"] = search_query

        if status:
            params["status"] = status

        return urlencode(params)

    def get_estimate_dashboard_summary(self):
        queryset = self.get_base_queryset()
        total = queryset.count()
        status_colors = self.get_status_color_map()
        current_status = (self.request.GET.get("status") or "").strip()

        items = []
        gradient_parts = []
        current_degree = 0
        used_degrees = 0

        for group in ESTIMATE_DASHBOARD_STATUS_GROUPS:
            status_key = group["key"]
            label = group["label"]
            count = queryset.filter(status__in=group["statuses"]).count()
            percent = round((count / total) * 100) if total else 0
            degrees = (count / total) * 360 if total else 0
            next_degree = current_degree + degrees
            color = status_colors.get(status_key, "#94a3b8")

            if count > 0:
                gradient_parts.append(
                    f"{color} {current_degree:.2f}deg {next_degree:.2f}deg"
                )
                used_degrees = next_degree

            items.append(
                {
                    "status": status_key,
                    "label": label,
                    "count": count,
                    "percent": percent,
                    "color": color,
                    "query_string": self.build_status_query_string(status_key),
                    "is_active": current_status == status_key,
                    "is_zero": count == 0,
                }
            )

            current_degree = next_degree

        if gradient_parts and used_degrees < 360:
            gradient_parts.append(f"#e5e7eb {used_degrees:.2f}deg 360deg")

        if gradient_parts:
            chart_gradient = ", ".join(gradient_parts)
        else:
            chart_gradient = "#e5e7eb 0deg 360deg"

        return {
            "total": total,
            "items": items,
            "chart_gradient": chart_gradient,
            "all_query_string": self.build_status_query_string(None),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Estimates"
        context["can_create_estimates"] = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_CREATE,
        )
        context["can_edit_estimates"] = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_EDIT,
        )
        context["can_delete_estimates"] = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_DELETE,
        )
        context["can_approve_estimates"] = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_APPROVE,
        )
        context["estimate_dashboard_summary"] = self.get_estimate_dashboard_summary()
        context["status_filter_options"] = [(group["key"], group["label"]) for group in ESTIMATE_DASHBOARD_STATUS_GROUPS]
        context["current_status_filter"] = self.request.GET.get("status", "")
        context["current_search_query"] = self.request.GET.get("q", "")

        company_slug = self.kwargs.get("company_slug")
        context["estimate_list_url"] = reverse_estimate_url(
            self.request,
            "estimate_list",
            company_slug=company_slug,
        )
        context["estimate_create_url"] = reverse_estimate_url(
            self.request,
            "estimate_create",
            company_slug=company_slug,
        )

        for estimate in context.get("estimates", []):
            estimate.ui_urls = build_estimate_action_urls(
                self.request,
                estimate,
                company_slug=company_slug,
            )

        return context


class EstimateDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "estimates"
    permission_required = PERMISSION_VIEW
    model = Estimate
    template_name = "estimates/detail.html"
    context_object_name = "estimate"
    pk_url_kwarg = "id_estimate"
    login_url = "/login/"

    def get_queryset(self):
        return estimate_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estimate = self.object

        can_edit = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_EDIT,
        )
        can_delete = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_DELETE,
        )
        can_approve = user_can_module_action(
            self.request.user,
            "estimates",
            PERMISSION_APPROVE,
        )

        context["page_title"] = "Estimate Details"
        context["public_estimate_url"] = build_public_estimate_url(
            request=self.request,
            estimate=estimate,
            company_slug=self.kwargs.get("company_slug"),
        )
        context["estimate_public_can_decide"] = can_customer_decide_estimate(estimate)
        context["can_edit_estimates"] = can_edit
        context["can_delete_estimates"] = can_delete
        context["can_approve_estimates"] = can_approve

        context["estimate_can_edit"] = (
            can_edit
            and estimate.status in ESTIMATE_EDIT_ALLOWED_STATUSES
        )

        context["estimate_can_send"] = (
            can_edit
            and estimate.status in [
                ESTIMATE_STATUS_PENDING,
                ESTIMATE_STATUS_PENDING_SEND,
            ]
        )

        context["estimate_can_resend"] = (
            can_edit
            and estimate.status in ESTIMATE_RESEND_ALLOWED_STATUSES
        )

        context["estimate_can_decide"] = (
            can_approve
            and estimate.status in [
                ESTIMATE_STATUS_SENT,
                ESTIMATE_STATUS_VIEWED,
            ]
        )

        project_sync_changes = get_estimate_project_sync_changes(estimate)

        context["estimate_project_sync_changes"] = project_sync_changes
        context["estimate_has_project_changes"] = bool(project_sync_changes)

        context["estimate_can_create_project"] = (
            estimate.status == ESTIMATE_STATUS_APPROVED
            and not estimate.id_project_id
        )

        context["estimate_has_project"] = bool(estimate.id_project_id)

        context["estimate_can_update_project"] = (
            can_edit
            and estimate.id_project_id
            and bool(project_sync_changes)
            and estimate.status != ESTIMATE_STATUS_CANCELLED
        )

        context["estimate_can_delete"] = (
            can_delete
            and estimate.status == ESTIMATE_STATUS_DRAFT
        )

        context["estimate_can_cancel"] = (
            can_approve
            and estimate.status in ESTIMATE_CANCEL_ALLOWED_STATUSES
        )
        context["estimate_can_toggle_pdf_style"] = can_edit

        company_slug = self.kwargs.get("company_slug")
        context["estimate_list_url"] = reverse_estimate_url(
            self.request,
            "estimate_list",
            company_slug=company_slug,
        )
        context["estimate_urls"] = build_estimate_action_urls(
            self.request,
            estimate,
            company_slug=company_slug,
        )
        context["open_project_url"] = context["estimate_urls"]["project_open"]

        return context


class EstimateCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "estimates"
    permission_required = PERMISSION_CREATE
    model = Estimate
    form_class = EstimateForm
    template_name = "estimates/form.html"
    success_url = reverse_lazy("estimates:estimate_list")
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        self.inspection = None
        self.object = None
        id_project = self.kwargs.get("id_project")
        id_assignment = self.kwargs.get("id_assignment")

        if id_project:
            self.project = get_object_or_404(
                project_queryset_for_user(request.user),
                id_project=id_project,
            )

        if id_assignment:
            assignment_queryset = InspectionAssignment.objects.select_related(
                "client",
                "client__id_company",
            )
            if not request.user.is_superuser:
                assignment_queryset = assignment_queryset.filter(
                    client__id_company_id=request.user.id_company_id,
                )
            self.inspection = get_object_or_404(
                assignment_queryset,
                id_assignment=id_assignment,
                status="completed",
            )

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["project"] = self.project
        kwargs["inspection"] = self.inspection
        return kwargs

    def get_item_formset(self):
        if self.request.method == "POST":
            return EstimateItemFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object,
                prefix="items",
            )

        return EstimateItemFormSet(
            instance=self.object,
            prefix="items",
        )

    def get_success_url(self):
        return reverse_estimate_url(
            request=self.request,
            view_name="estimate_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_estimate": self.object.id_estimate},
        )

    def post(self, request, *args, **kwargs):
        self.object = None

        form = self.get_form()
        item_formset = self.get_item_formset()

        if form.is_valid() and item_formset.is_valid():
            return self.forms_valid(form, item_formset)

        return self.forms_invalid(form, item_formset)

    def forms_valid(self, form, item_formset):
        self.object = form.save(commit=False)
        self.object.status = get_requested_estimate_status(self.request)
        self.object.save()

        item_formset.instance = self.object
        item_formset.save()

        recalculate_estimate(self.object)

        if self.request.POST.get("update_project_after_save") == "1" and self.object.id_project_id:
            updated_labels = update_project_from_estimate(self.object, self.request.user)
            if updated_labels:
                messages.success(self.request, "Linked project updated: " + ", ".join(updated_labels) + ".")
            else:
                messages.info(self.request, "The linked project was already up to date.")

        if self.object.status == ESTIMATE_STATUS_DRAFT:
            messages.success(self.request, "Draft estimate saved successfully.")
        else:
            messages.success(self.request, "Proforma saved and ready to send.")

        return redirect(self.get_success_url())

    def forms_invalid(self, form, item_formset):
        messages.error(self.request, "Please review the estimate form and items.")

        return self.render_to_response(
            self.get_context_data(
                form=form,
                item_formset=item_formset,
            )
        )

    def form_invalid(self, form):
        item_formset = self.get_item_formset()

        return self.forms_invalid(form, item_formset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "item_formset" not in context:
            context["item_formset"] = self.get_item_formset()

        context["page_title"] = "Create Estimate"
        context["form_title"] = "Create Estimate"
        if self.inspection:
            context["page_title"] = "Create Estimate From Inspection"
            context["form_title"] = "Create Estimate From Inspection"
        context["submit_label"] = "Save Estimate"
        context["project"] = self.project
        context["inspection"] = self.inspection
        context["show_draft_button"] = True
        context["show_proforma_button"] = True
        context["show_save_changes_button"] = False
        context["cancel_url"] = reverse_estimate_url(
            request=self.request,
            view_name="estimate_list",
            company_slug=self.kwargs.get("company_slug"),
        )
        context["estimate_projects_api_url"] = reverse_estimate_url(
            request=self.request,
            view_name="estimate_projects_for_client",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_client": 0},
        )
        if self.inspection:
            context["form_action_url"] = reverse_estimate_url(
                request=self.request,
                view_name="estimate_create_from_inspection",
                company_slug=self.kwargs.get("company_slug"),
                kwargs={"id_assignment": self.inspection.id_assignment},
            )
        elif self.project:
            context["form_action_url"] = reverse_estimate_url(
                request=self.request,
                view_name="estimate_create_for_project",
                company_slug=self.kwargs.get("company_slug"),
                kwargs={"id_project": self.project.id_project},
            )
        else:
            context["form_action_url"] = reverse_estimate_url(
                request=self.request,
                view_name="estimate_create",
                company_slug=self.kwargs.get("company_slug"),
            )

        return context


class EstimateUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "estimates"
    permission_required = PERMISSION_EDIT
    model = Estimate
    form_class = EstimateForm
    template_name = "estimates/form.html"
    context_object_name = "estimate"
    pk_url_kwarg = "id_estimate"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.status not in ESTIMATE_EDIT_ALLOWED_STATUSES:
            messages.error(request, "This estimate can no longer be edited because it is approved, converted or cancelled.")
            return redirect_estimate_url(
                request,
                "estimate_detail",
                company_slug=self.kwargs.get("company_slug"),
                kwargs={"id_estimate": self.object.id_estimate},
            )

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return estimate_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_item_formset(self):
        if self.request.method == "POST":
            return EstimateItemFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object,
                prefix="items",
            )

        return EstimateItemFormSet(
            instance=self.object,
            prefix="items",
        )

    def get_success_url(self):
        return reverse_estimate_url(
            request=self.request,
            view_name="estimate_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_estimate": self.object.id_estimate},
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = self.get_form()
        item_formset = self.get_item_formset()

        if form.is_valid() and item_formset.is_valid():
            return self.forms_valid(form, item_formset)

        return self.forms_invalid(form, item_formset)

    def forms_valid(self, form, item_formset):
        previous_status = self.object.status

        self.object = form.save(commit=False)
        self.object.status = get_requested_estimate_status(
            self.request,
            current_status=previous_status,
        )
        self.object.save()

        item_formset.instance = self.object
        item_formset.save()

        recalculate_estimate(self.object)

        if previous_status == ESTIMATE_STATUS_REJECTED:
            reopen_rejected_estimate_after_edit(self.object, self.request.user)
            messages.info(
                self.request,
                "Rejected estimate edited. A new customer review link was generated and the estimate is ready to resend.",
            )

        if self.object.status in [ESTIMATE_STATUS_PENDING, ESTIMATE_STATUS_PENDING_SEND]:
            self.object.viewed_at = None
            self.object.approved_at = None
            self.object.rejected_at = None
            self.object.rejection_reason = ""
            self.object.save(
                update_fields=[
                    "viewed_at",
                    "approved_at",
                    "rejected_at",
                    "rejection_reason",
                    "last_modified_at",
                ]
            )

        if self.request.POST.get("update_project_after_save") == "1" and self.object.id_project_id:
            updated_labels = update_project_from_estimate(self.object, self.request.user)
            if updated_labels:
                messages.success(self.request, "Linked project updated: " + ", ".join(updated_labels) + ".")
            else:
                messages.info(self.request, "The linked project was already up to date.")

        messages.success(self.request, "Estimate updated successfully.")

        return redirect(self.get_success_url())

    def forms_invalid(self, form, item_formset):
        messages.error(self.request, "Please review the estimate form and items.")

        return self.render_to_response(
            self.get_context_data(
                form=form,
                item_formset=item_formset,
            )
        )

    def form_invalid(self, form):
        item_formset = self.get_item_formset()

        return self.forms_invalid(form, item_formset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "item_formset" not in context:
            context["item_formset"] = self.get_item_formset()

        estimate = self.object

        context["page_title"] = "Edit Estimate"
        context["form_title"] = "Edit Estimate"
        context["submit_label"] = "Update Estimate"
        context["project"] = estimate.id_project
        context["show_draft_button"] = estimate.status == ESTIMATE_STATUS_DRAFT
        context["show_proforma_button"] = estimate.status == ESTIMATE_STATUS_DRAFT
        context["show_save_changes_button"] = estimate.status in ESTIMATE_EDIT_ALLOWED_STATUSES and estimate.status != ESTIMATE_STATUS_DRAFT
        context["cancel_url"] = reverse_estimate_url(
            request=self.request,
            view_name="estimate_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_estimate": estimate.id_estimate},
        )
        context["estimate_projects_api_url"] = reverse_estimate_url(
            request=self.request,
            view_name="estimate_projects_for_client",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_client": 0},
        )
        context["form_action_url"] = reverse_estimate_url(
            request=self.request,
            view_name="estimate_update",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_estimate": estimate.id_estimate},
        )

        return context


class EstimateSendView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "estimates"
    permission_required = PERMISSION_EDIT
    template_name = "estimates/send.html"
    login_url = "/login/"

    def get_estimate(self, request, id_estimate):
        return get_object_or_404(
            estimate_list_for_user(request.user),
            id_estimate=id_estimate,
        )

    def validate_send_allowed(self, request, estimate):
        allowed_send_statuses = set(ESTIMATE_SEND_ALLOWED_STATUSES) | set(
            ESTIMATE_RESEND_ALLOWED_STATUSES
        )

        if estimate.status not in allowed_send_statuses:
            messages.error(request, "This estimate cannot be sent in its current status.")
            return False

        return True

    def get_initial_email(self, estimate):
        if getattr(estimate, "client_billing_email", None):
            return estimate.client_billing_email

        client = estimate.id_client

        possible_fields = [
            "email",
            "client_email",
            "billing_email",
            "contact_email",
        ]

        for field_name in possible_fields:
            value = getattr(client, field_name, None)

            if value:
                return value

        return ""

    def get_context(self, request, estimate, form, company_slug=None):
        estimate_urls = build_estimate_action_urls(
            request,
            estimate,
            company_slug=company_slug,
        )
        return {
            "estimate": estimate,
            "form": form,
            "is_resend": estimate.status in ESTIMATE_RESEND_ALLOWED_STATUSES,
            "public_estimate_url": build_public_estimate_url(
                request=request,
                estimate=estimate,
                company_slug=company_slug,
            ),
            "estimate_detail_url": estimate_urls["detail"],
            "send_form_action_url": estimate_urls["send"],
        }

    def get(self, request, id_estimate, company_slug=None):
        estimate = self.get_estimate(request, id_estimate)

        if not self.validate_send_allowed(request, estimate):
            return redirect(
                reverse_estimate_url(
                    request=request,
                    view_name="estimate_detail",
                    company_slug=company_slug,
                    kwargs={"id_estimate": estimate.id_estimate},
                )
            )

        form = EstimateSendEmailForm(
            initial={
                "recipient_email": self.get_initial_email(estimate),
                "subject": f"Estimate {getattr(estimate, 'estimate_number', '') or estimate.id_estimate}",
                "message": "Please review the estimate details.",
            }
        )

        return render(
            request,
            self.template_name,
            self.get_context(
                request,
                estimate,
                form,
                company_slug=company_slug,
            ),
        )

    def post(self, request, id_estimate, company_slug=None):
        estimate = self.get_estimate(request, id_estimate)

        if not self.validate_send_allowed(request, estimate):
            return redirect(
                reverse_estimate_url(
                    request=request,
                    view_name="estimate_detail",
                    company_slug=company_slug,
                    kwargs={"id_estimate": estimate.id_estimate},
                )
            )

        form = EstimateSendEmailForm(request.POST)

        if form.is_valid():
            try:
                if estimate.status == ESTIMATE_STATUS_REJECTED:
                    refresh_public_estimate_token(estimate, force=True)

                public_estimate_url = build_public_estimate_url(
                    request=request,
                    estimate=estimate,
                    company_slug=company_slug,
                )

                send_estimate_to_email(
                    estimate=estimate,
                    recipient_email=form.cleaned_data["recipient_email"],
                    subject=form.cleaned_data.get("subject", ""),
                    message=form.cleaned_data.get("message", ""),
                    user=request.user,
                    public_estimate_url=public_estimate_url,
                )

                messages.success(
                    request,
                    f"Estimate {getattr(estimate, 'estimate_number', '') or estimate.id_estimate} sent successfully.",
                )

                return redirect(
                    reverse_estimate_url(
                        request=request,
                        view_name="estimate_detail",
                        company_slug=company_slug,
                        kwargs={"id_estimate": estimate.id_estimate},
                    )
                )

            except Exception as error:
                messages.error(
                    request,
                    f"Estimate could not be sent: {error}",
                )

        return render(
            request,
            self.template_name,
            self.get_context(
                request,
                estimate,
                form,
                company_slug=company_slug,
            ),
        )


@require_POST
def estimate_approve_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user).select_related(
            "id_company",
            "id_client",
            "id_project",
        ),
        id_estimate=id_estimate,
    )

    should_create_project = request.POST.get("create_project") == "1"
    should_update_project = request.POST.get("update_project") == "1"

    try:
        if estimate.status != ESTIMATE_STATUS_APPROVED:
            estimate_approve(estimate)
            estimate.refresh_from_db()

        messages.success(request, "Estimate approved successfully.")

        if estimate.id_project_id:
            if should_create_project:
                messages.info(
                    request,
                    "This estimate is already linked to a project. A second project cannot be created from the same estimate.",
                )

            if should_update_project:
                updated_labels = update_project_from_estimate(estimate, request.user)

                if updated_labels:
                    messages.success(
                        request,
                        "Linked project updated: " + ", ".join(updated_labels) + ".",
                    )
                else:
                    messages.info(request, "The linked project was already up to date.")

            return redirect_estimate_url(
                request,
                "estimate_detail",
                company_slug=company_slug,
                kwargs={"id_estimate": estimate.id_estimate},
            )

        if should_create_project:
            return redirect_estimate_url(
                request,
                "estimate_project_create",
                company_slug=company_slug,
                kwargs={"id_estimate": estimate.id_estimate},
            )

    except Exception as error:
        messages.error(request, f"Estimate could not be approved: {error}")

    return redirect_estimate_url(
        request,
        "estimate_detail",
        company_slug=company_slug,
        kwargs={"id_estimate": estimate.id_estimate},
    )


@require_POST
def estimate_reject_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user),
        id_estimate=id_estimate,
    )

    try:
        reason = request.POST.get("rejection_reason", "").strip()
        estimate_reject(estimate, reason=reason)
        messages.success(request, "Estimate rejected successfully.")
    except Exception as error:
        messages.error(request, f"Estimate could not be rejected: {error}")

    return redirect_estimate_url(
        request,
        "estimate_detail",
        company_slug=company_slug,
        kwargs={"id_estimate": estimate.id_estimate},
    )


@require_POST
def estimate_cancel_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user),
        id_estimate=id_estimate,
    )

    if estimate.status not in ESTIMATE_CANCEL_ALLOWED_STATUSES:
        messages.error(request, "Approved, converted or already cancelled estimates cannot be cancelled.")
        return redirect_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs={"id_estimate": estimate.id_estimate},
        )

    reason = request.POST.get("void_reason", "").strip()

    try:
        estimate_cancel(estimate)
        messages.success(request, "Estimate voided successfully.")
        return redirect_estimate_url(
            request,
            "estimate_list",
            company_slug=company_slug,
        )
    except Exception as error:
        messages.error(request, f"Estimate could not be voided: {error}")
        return redirect_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs={"id_estimate": estimate.id_estimate},
        )


@require_POST
def estimate_delete_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_DELETE,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user),
        id_estimate=id_estimate,
    )

    if estimate.status != ESTIMATE_STATUS_DRAFT:
        messages.error(request, "Only draft estimates can be deleted.")
        return redirect_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs={"id_estimate": estimate.id_estimate},
        )

    estimate.delete()
    messages.success(request, "Draft estimate deleted successfully.")

    return redirect_estimate_url(
        request,
        "estimate_list",
        company_slug=company_slug,
    )


@require_POST
def estimate_project_update_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user).select_related(
            "id_company",
            "id_client",
            "id_project",
        ),
        id_estimate=id_estimate,
    )

    if not estimate.id_project_id:
        messages.error(request, "This estimate is not linked to an existing project.")
        return redirect_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs={"id_estimate": estimate.id_estimate},
        )

    if estimate.status == ESTIMATE_STATUS_CANCELLED:
        messages.error(request, "Cancelled estimates cannot update linked projects.")
        return redirect_estimate_url(
            request,
            "estimate_detail",
            company_slug=company_slug,
            kwargs={"id_estimate": estimate.id_estimate},
        )

    try:
        with transaction.atomic():
            locked_project = Project.objects.select_for_update().get(
                id_project=estimate.id_project_id,
                id_company_id=estimate.id_company_id,
                id_client_id=estimate.id_client_id,
            )
            estimate.id_project = locked_project
            updated_labels = update_project_from_estimate(estimate, request.user)

        if updated_labels:
            messages.success(
                request,
                "Linked project updated: " + ", ".join(updated_labels) + ".",
            )
        else:
            messages.info(request, "The linked project was already up to date.")

    except Project.DoesNotExist:
        messages.error(request, "The linked project does not belong to this estimate client/company.")
    except Exception as error:
        messages.error(request, f"Linked project could not be updated: {error}")

    if request.POST.get("next") == "project" and estimate.id_project_id:
        return redirect_project_url(
            request,
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": estimate.id_project_id},
        )

    return redirect_estimate_url(
        request,
        "estimate_detail",
        company_slug=company_slug,
        kwargs={"id_estimate": estimate.id_estimate},
    )


class EstimateProjectCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "projects"
    permission_required = PERMISSION_CREATE
    template_name = "estimates/project_create_from_estimate.html"
    login_url = "/login/"

    def get_estimate(self, request, id_estimate):
        return get_object_or_404(
            estimate_list_for_user(request.user).select_related(
                "id_company",
                "id_client",
                "id_project",
                "id_inspection_assignment",
            ).prefetch_related("items"),
            id_estimate=id_estimate,
        )

    def ensure_can_create_project(self, request, estimate, company_slug=None):
        if estimate.id_project_id:
            messages.error(
                request,
                "This estimate already has a project. A second project cannot be created from the same estimate.",
            )
            return redirect_project_url(
                request,
                "project_detail",
                company_slug=company_slug,
                kwargs={"id_project": estimate.id_project_id},
            )

        if estimate.status != ESTIMATE_STATUS_APPROVED:
            messages.error(
                request,
                "Only approved estimates can be converted into a project.",
            )
            return redirect_estimate_url(
                request,
                "estimate_detail",
                company_slug=company_slug,
                kwargs={"id_estimate": estimate.id_estimate},
            )

        return None

    def build_form(self, request, estimate, data=None):
        kwargs = {
            "user": request.user,
            "initial": get_estimate_project_initial(estimate),
        }

        if data is not None:
            kwargs["data"] = data

        form = ProjectForm(**kwargs)
        form.fields["id_client"].initial = estimate.id_client
        form.fields["id_client"].disabled = True

        return form

    def get_context(self, request, estimate, form, company_slug=None):
        return {
            "form": form,
            "estimate": estimate,
            "page_title": "Create Project From Estimate",
            "form_title": "Create Project From Estimate",
            "submit_label": "Save Project",
            "cancel_url": reverse_estimate_url(
                request=request,
                view_name="estimate_detail",
                company_slug=company_slug,
                kwargs={"id_estimate": estimate.id_estimate},
            ),
            "form_action_url": reverse_estimate_url(
                request=request,
                view_name="estimate_project_create",
                company_slug=company_slug,
                kwargs={"id_estimate": estimate.id_estimate},
            ),
        }

    def get(self, request, id_estimate, company_slug=None):
        estimate = self.get_estimate(request, id_estimate)
        redirect_response = self.ensure_can_create_project(request, estimate, company_slug)

        if redirect_response:
            return redirect_response

        form = self.build_form(request, estimate)

        return render(
            request,
            self.template_name,
            self.get_context(request, estimate, form, company_slug),
        )

    def post(self, request, id_estimate, company_slug=None):
        estimate = self.get_estimate(request, id_estimate)
        redirect_response = self.ensure_can_create_project(request, estimate, company_slug)

        if redirect_response:
            return redirect_response

        form = self.build_form(request, estimate, data=request.POST)

        if not form.is_valid():
            messages.error(request, "Please review the project form.")
            return render(
                request,
                self.template_name,
                self.get_context(request, estimate, form, company_slug),
            )

        with transaction.atomic():
            # Lock only the estimate row. Do not use select_related() here because
            # id_project is nullable and PostgreSQL raises:
            # "FOR UPDATE cannot be applied to the nullable side of an outer join".
            locked_estimate = (
                Estimate.objects.select_for_update(of=("self",))
                .get(id_estimate=estimate.id_estimate)
            )

            if locked_estimate.id_project_id:
                messages.error(
                    request,
                    "This estimate already has a project. A second project cannot be created from the same estimate.",
                )
                return redirect_project_url(
                    request,
                    "project_detail",
                    company_slug=company_slug,
                    kwargs={"id_project": locked_estimate.id_project_id},
                )

            project = form.save()

            locked_estimate.id_project = project
            locked_estimate.project_name = project.name
            locked_estimate.project_address = project.project_address
            locked_estimate.status = ESTIMATE_STATUS_CONVERTED
            locked_estimate.converted_at = timezone.now()

            if request.user.is_authenticated:
                locked_estimate.updated_by = request.user

            locked_estimate.save(
                update_fields=[
                    "id_project",
                    "project_name",
                    "project_address",
                    "status",
                    "converted_at",
                    "updated_by",
                    "last_modified_at",
                ]
            )

            if locked_estimate.id_inspection_assignment_id:
                InspectionAssignment.objects.filter(
                    id_assignment=locked_estimate.id_inspection_assignment_id,
                    client__id_company_id=project.id_company_id,
                ).update(id_project=project)

        messages.success(
            request,
            "Project created successfully from this estimate.",
        )

        return redirect_project_url(
            request,
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": project.id_project},
        )


@require_http_methods(["GET", "POST"])
def estimate_pdf_style_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        estimate_list_for_user(request.user),
        id_estimate=id_estimate,
    )

    if request.method == "POST":
        estimate.pdf_header_dark = request.POST.get("pdf_header_dark") in ["1", "on", "true", "True", "yes"]
    else:
        # Fallback for cached links or browser navigation to /pdf-style/.
        # It avoids a hard 405 and still performs the intended toggle.
        requested_value = request.GET.get("pdf_header_dark")
        if requested_value in ["0", "1", "on", "true", "false"]:
            estimate.pdf_header_dark = requested_value in ["1", "on", "true"]
        else:
            estimate.pdf_header_dark = not bool(estimate.pdf_header_dark)

    estimate.save(update_fields=["pdf_header_dark", "last_modified_at"])
    messages.success(request, "Estimate PDF logo background updated successfully.")
    return redirect_estimate_url(
        request,
        "estimate_detail",
        company_slug=company_slug,
        kwargs={"id_estimate": estimate.id_estimate},
    )


@require_GET
def estimate_pdf_view(request, id_estimate, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "estimates",
        PERMISSION_VIEW,
    )

    if permission_response:
        return permission_response

    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
        ),
        id_estimate=id_estimate,
    )

    if not user_can_access_estimate(request.user, estimate):
        return HttpResponseForbidden("Permission denied.")

    return estimate_pdf_response(estimate)


@never_cache
@xframe_options_deny
@require_GET
def public_estimate_preview_view(request, token, company_slug=None):
    """
    Public estimate preview for customers.
    No CRM login required. Access is protected by public_token.
    """
    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
        ).prefetch_related(
            "items",
        ),
        public_token=token,
    )

    mark_estimate_as_viewed_publicly(estimate)
    estimate.refresh_from_db()
    recalculate_estimate(estimate)

    return render(
        request,
        "estimates/public_preview.html",
        get_public_estimate_context(
            request,
            estimate,
            company_slug=company_slug,
            page_title=f"Estimate {estimate.estimate_number or estimate.id_estimate}",
        ),
    )


@never_cache
@xframe_options_deny
@require_POST
def public_estimate_approve_view(request, token, company_slug=None):
    estimate = get_public_estimate_by_token(token)

    try:
        approve_estimate_publicly(estimate)
        estimate.refresh_from_db()

        return render(
            request,
            "estimates/public_result.html",
            {
                "estimate": estimate,
                "result_title": "Estimate Approved",
                "result_message": "Thank you. Your estimate has been approved successfully.",
                "result_type": "success",
                "public_preview_url": reverse_estimate_url(
                    request,
                    "public_estimate_preview",
                    company_slug=company_slug,
                    kwargs={"token": estimate.public_token},
                ),
            },
        )

    except EstimatePublicFlowError as error:
        return render(
            request,
            "estimates/public_preview.html",
            get_public_estimate_context(
                request,
                estimate,
                company_slug=company_slug,
                page_title="Estimate Review",
                decision_error=str(error),
            ),
        )


@never_cache
@xframe_options_deny
@require_POST
def public_estimate_reject_view(request, token, company_slug=None):
    estimate = get_public_estimate_by_token(token)

    if request.method != "POST":
        return redirect_estimate_url(
            request,
            "public_estimate_preview",
            company_slug=company_slug,
            kwargs={"token": estimate.public_token},
        )

    rejection_reason = request.POST.get("rejection_reason", "").strip()

    try:
        reject_estimate_publicly(
            estimate=estimate,
            reason=rejection_reason,
        )
        estimate.refresh_from_db()

        return render(
            request,
            "estimates/public_result.html",
            {
                "estimate": estimate,
                "result_title": "Estimate Rejected",
                "result_message": "Your rejection reason has been submitted successfully.",
                "result_type": "danger",
                "public_preview_url": reverse_estimate_url(
                    request,
                    "public_estimate_preview",
                    company_slug=company_slug,
                    kwargs={"token": estimate.public_token},
                ),
            },
        )

    except EstimatePublicFlowError as error:
        return render(
            request,
            "estimates/public_preview.html",
            get_public_estimate_context(
                request,
                estimate,
                company_slug=company_slug,
                page_title="Estimate Review",
                rejection_error=str(error),
                rejection_reason=rejection_reason,
            ),
        )


class EstimateViewSet(TenantModelViewSet):
    module_name = "estimates"
    queryset = Estimate.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
    ).all()
    serializer_class = EstimateSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return estimate_list_for_user(self.request.user)

    def perform_create(self, serializer):
        company = serializer.validated_data.get("id_company")
        client = serializer.validated_data.get("id_client")
        project = serializer.validated_data.get("id_project")

        if not self.request.user.is_superuser:
            company = self.request.user.id_company

        if not company:
            raise PermissionDenied("Company is required.")

        if client and client.id_company_id != company.id_company:
            raise PermissionDenied("Client must belong to the selected company.")

        if project and project.id_company_id != company.id_company:
            raise PermissionDenied("Project must belong to the selected company.")

        if project and client and project.id_client_id != client.id_client:
            raise PermissionDenied("Project must belong to the selected client.")

        serializer.save(id_company=company)
        recalculate_estimate(serializer.instance)

    def perform_update(self, serializer):
        instance = self.get_object()

        if not user_can_access_estimate(self.request.user, instance):
            raise PermissionDenied("You can only update estimates from your company.")

        if instance.status not in ESTIMATE_EDIT_ALLOWED_STATUSES:
            raise PermissionDenied("This estimate can no longer be edited because it is approved, converted or cancelled.")

        serializer.save()
        recalculate_estimate(serializer.instance)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not user_can_module_action(request.user, "estimates", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to approve estimates.")

        estimate = self.get_object()
        estimate_approve(estimate)

        return Response(
            {
                "detail": "Estimate approved successfully.",
                "estimate_id": estimate.id_estimate,
                "status": estimate.status,
            }
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not user_can_module_action(request.user, "estimates", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to reject estimates.")

        estimate = self.get_object()
        estimate_reject(estimate)

        return Response(
            {
                "detail": "Estimate rejected successfully.",
                "estimate_id": estimate.id_estimate,
                "status": estimate.status,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if not user_can_module_action(request.user, "estimates", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to cancel estimates.")

        estimate = self.get_object()
        estimate_cancel(estimate)

        return Response(
            {
                "detail": "Estimate cancelled successfully.",
                "estimate_id": estimate.id_estimate,
                "status": estimate.status,
            }
        )