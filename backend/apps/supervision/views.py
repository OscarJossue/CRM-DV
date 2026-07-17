from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.dashboard_ui import build_dashboard_items
from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)
from apps.inspections.models import InspectionAssignment
from apps.projects.selectors import project_list_for_user

from .forms import SupervisionForm
from .models import Supervision
from .permissions import user_can_access_supervision
from .selectors import supervision_list_for_user
from .serializers import SupervisionSerializer
from .services import (
    supervision_approve,
    supervision_mark_final_audit,
    supervision_reject,
)


def _company_slug(request, explicit=None):
    if explicit:
        return explicit
    company = getattr(request, "company", None) or getattr(request.user, "id_company", None)
    return getattr(company, "slug", None) or getattr(company, "company_slug", None)


def reverse_supervision_url(request, view_name, *, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    namespace = getattr(getattr(request, "resolver_match", None), "namespace", "")
    use_company = namespace == "company_supervision" or bool(_company_slug(request, company_slug))
    if use_company:
        slug = _company_slug(request, company_slug)
        if slug:
            kwargs["company_slug"] = slug
            return reverse(f"company_supervision:{view_name}", kwargs=kwargs)
    return reverse(f"supervision:{view_name}", kwargs=kwargs)


def reverse_target_url(request, supervision, company_slug=None):
    slug = _company_slug(request, company_slug)
    if supervision.id_project_id:
        kwargs = {"id_project": supervision.id_project_id}
        if slug:
            kwargs["company_slug"] = slug
            return reverse("company_projects:project_detail", kwargs=kwargs)
        return reverse("projects:project_detail", kwargs=kwargs)

    kwargs = {"id_assignment": supervision.id_inspection_assignment_id}
    if slug:
        kwargs["company_slug"] = slug
        return reverse("company_inspections:inspection_detail", kwargs=kwargs)
    return reverse("inspections:inspection_detail", kwargs=kwargs)


def attach_supervision_urls(request, supervision, company_slug=None):
    base_kwargs = {"id_supervision": supervision.id_supervision}
    supervision.detail_url = reverse_supervision_url(
        request, "supervision_detail", company_slug=company_slug, kwargs=base_kwargs
    )
    supervision.edit_url = reverse_supervision_url(
        request, "supervision_update", company_slug=company_slug, kwargs=base_kwargs
    )
    supervision.approve_url = reverse_supervision_url(
        request, "supervision_approve", company_slug=company_slug, kwargs=base_kwargs
    )
    supervision.reject_url = reverse_supervision_url(
        request, "supervision_reject", company_slug=company_slug, kwargs=base_kwargs
    )
    supervision.final_audit_url = reverse_supervision_url(
        request, "supervision_final_audit", company_slug=company_slug, kwargs=base_kwargs
    )
    supervision.target_url = reverse_target_url(request, supervision, company_slug)
    return supervision


class SupervisionListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "supervision"
    permission_required = PERMISSION_VIEW
    template_name = "supervision/list.html"
    context_object_name = "supervisions"
    paginate_by = 25
    login_url = "/login/"

    def get_queryset(self):
        base_queryset = supervision_list_for_user(self.request.user)
        self.supervision_base_queryset = base_queryset
        queryset = base_queryset
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        target_type = (self.request.GET.get("target") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(id_project__project_code__icontains=token)
                    | Q(id_project__name__icontains=token)
                    | Q(id_project__id_client__client_code__icontains=token)
                    | Q(id_project__id_client__name__icontains=token)
                    | Q(id_inspection_assignment__client__client_code__icontains=token)
                    | Q(id_inspection_assignment__client__name__icontains=token)
                    | Q(id_inspection_assignment__inspection_notes__icontains=token)
                    | Q(id_supervisor__email__icontains=token)
                    | Q(observations__icontains=token)
                    | Q(rejection_reason__icontains=token)
                )

        if status == "pending":
            queryset = queryset.filter(approved=False, rejected=False, final_audit=False)
        elif status == "rejected":
            queryset = queryset.filter(rejected=True, final_audit=False)
        elif status == "approved":
            queryset = queryset.filter(approved=True, final_audit=False)
        elif status == "completed":
            queryset = queryset.filter(final_audit=True)

        if target_type == "project":
            queryset = queryset.filter(id_project__isnull=False)
        elif target_type == "inspection":
            queryset = queryset.filter(id_inspection_assignment__isnull=False)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Audit"
        context["can_create_supervision"] = user_can_module_action(
            self.request.user, "supervision", PERMISSION_CREATE
        )
        context["can_edit_supervision"] = user_can_module_action(
            self.request.user, "supervision", PERMISSION_EDIT
        )
        context["can_approve_supervision"] = user_can_module_action(
            self.request.user, "supervision", PERMISSION_APPROVE
        )
        company_slug = self.kwargs.get("company_slug")
        context["supervision_list_url"] = reverse_supervision_url(
            self.request, "supervision_list", company_slug=company_slug
        )
        context["supervision_create_url"] = reverse_supervision_url(
            self.request, "supervision_create", company_slug=company_slug
        )

        for supervision in context.get("supervisions", []):
            attach_supervision_urls(self.request, supervision, company_slug)
            if supervision.id_project_id:
                supervision.contractor = supervision.id_project.id_inspector
                supervision.evidence_count = (
                    supervision.id_project.evidence.count()
                    + supervision.id_project.gallery_images.count()
                )
            else:
                supervision.contractor = supervision.id_inspection_assignment.inspector
                supervision.evidence_count = supervision.id_inspection_assignment.gallery_images.count()
            if supervision.final_audit:
                supervision.status_label = "Audit completed"
                supervision.status_class = "is-success"
            elif supervision.rejected:
                supervision.status_label = "Corrections required"
                supervision.status_class = "is-danger"
            elif supervision.approved:
                supervision.status_label = "Approved"
                supervision.status_class = "is-info"
            else:
                supervision.status_label = "Pending audit"
                supervision.status_class = "is-warning"

        current_status = self.request.GET.get("status", "")
        current_target = self.request.GET.get("target", "")
        context["supervision_filters"] = {
            "q": self.request.GET.get("q", ""),
            "status": current_status,
            "target": current_target,
        }
        base_queryset = getattr(
            self, "supervision_base_queryset", supervision_list_for_user(self.request.user)
        )
        counts = {
            "pending": base_queryset.filter(
                approved=False, rejected=False, final_audit=False
            ).count(),
            "rejected": base_queryset.filter(rejected=True, final_audit=False).count(),
            "completed": base_queryset.filter(final_audit=True).count(),
        }
        context["supervision_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {
                    "value": "pending",
                    "label": "Pending audit",
                    "caption": "Field submissions waiting for review",
                    "icon": "bi-hourglass-split",
                    "color": "#f59e0b",
                },
                {
                    "value": "rejected",
                    "label": "Corrections",
                    "caption": "Returned to contractor",
                    "icon": "bi-arrow-counterclockwise",
                    "color": "#dc2626",
                },
                {
                    "value": "completed",
                    "label": "Completed",
                    "caption": "Final audit approved",
                    "icon": "bi-shield-check",
                    "color": "#0e9f6e",
                },
            ],
            counts,
            active_value=current_status,
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        context["supervision_filter_query"] = urlencode(params, doseq=True)
        return context


class SupervisionDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "supervision"
    permission_required = PERMISSION_VIEW
    model = Supervision
    template_name = "supervision/detail.html"
    context_object_name = "supervision"
    pk_url_kwarg = "id_supervision"
    login_url = "/login/"

    def get_queryset(self):
        return supervision_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supervision = self.object
        company_slug = self.kwargs.get("company_slug")
        attach_supervision_urls(self.request, supervision, company_slug)
        context["page_title"] = "Audit Review"
        context["can_edit_supervision"] = user_can_module_action(
            self.request.user, "supervision", PERMISSION_EDIT
        )
        context["can_approve_supervision"] = user_can_module_action(
            self.request.user, "supervision", PERMISSION_APPROVE
        )
        context["supervision_list_url"] = reverse_supervision_url(
            self.request, "supervision_list", company_slug=company_slug
        )

        if supervision.id_project_id:
            project = supervision.id_project
            context["project_evidence"] = project.evidence.select_related("uploaded_by").all()
            context["project_gallery"] = project.gallery_images.select_related("uploaded_by").all()
            context["project_notes"] = project.notes.select_related("created_by").all()
            supervision.evidence_count = (
                context["project_evidence"].count() + context["project_gallery"].count()
            )
        else:
            assignment = supervision.id_inspection_assignment
            context["inspection_gallery"] = assignment.gallery_images.select_related("uploaded_by").all()
            supervision.evidence_count = context["inspection_gallery"].count()

        return context


class SupervisionCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "supervision"
    permission_required = PERMISSION_CREATE
    model = Supervision
    form_class = SupervisionForm
    template_name = "supervision/form.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        self.inspection = None
        id_project = self.kwargs.get("id_project")
        id_assignment = self.kwargs.get("id_assignment")
        if id_project:
            self.project = get_object_or_404(
                project_list_for_user(request.user), id_project=id_project
            )
        if id_assignment:
            queryset = InspectionAssignment.objects.select_related("client", "client__id_company")
            if not request.user.is_superuser:
                queryset = queryset.filter(client__id_company_id=request.user.id_company_id)
            self.inspection = get_object_or_404(queryset, id_assignment=id_assignment)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            user=self.request.user,
            project=self.project,
            inspection=self.inspection,
        )
        return kwargs

    def get_success_url(self):
        return reverse_supervision_url(
            self.request,
            "supervision_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_supervision": self.object.id_supervision},
        )

    def form_valid(self, form):
        messages.success(self.request, "Audit record created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the audit form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title="Create Audit",
            form_title="Create Audit",
            submit_label="Save Audit",
            project=self.project,
            inspection=self.inspection,
            cancel_url=reverse_supervision_url(
                self.request,
                "supervision_list",
                company_slug=self.kwargs.get("company_slug"),
            ),
        )
        return context


class SupervisionUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "supervision"
    permission_required = PERMISSION_EDIT
    model = Supervision
    form_class = SupervisionForm
    template_name = "supervision/form.html"
    context_object_name = "supervision"
    pk_url_kwarg = "id_supervision"
    login_url = "/login/"

    def get_queryset(self):
        return supervision_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_supervision_url(
            self.request,
            "supervision_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_supervision": self.object.id_supervision},
        )

    def form_valid(self, form):
        messages.success(self.request, "Audit updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the audit form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title="Edit Audit",
            form_title="Edit Audit",
            submit_label="Update Audit",
            project=self.object.id_project,
            inspection=self.object.id_inspection_assignment,
            cancel_url=self.get_success_url(),
        )
        return context


def _audit_action_object(request, id_supervision):
    supervision = get_object_or_404(
        supervision_list_for_user(request.user), id_supervision=id_supervision
    )
    if not user_can_access_supervision(request.user, supervision):
        return None
    return supervision


def _redirect_audit_detail(request, supervision, company_slug=None):
    return redirect(
        reverse_supervision_url(
            request,
            "supervision_detail",
            company_slug=company_slug,
            kwargs={"id_supervision": supervision.id_supervision},
        )
    )


@require_POST
def supervision_approve_view(request, id_supervision, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user, "supervision", PERMISSION_APPROVE
    )
    if permission_response:
        return permission_response
    supervision = _audit_action_object(request, id_supervision)
    if not supervision:
        return HttpResponseForbidden("Permission denied.")
    supervision_approve(supervision)
    messages.success(request, "Evidence review approved. Complete the final audit to close the work.")
    return _redirect_audit_detail(request, supervision, company_slug)


@require_POST
def supervision_reject_view(request, id_supervision, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user, "supervision", PERMISSION_APPROVE
    )
    if permission_response:
        return permission_response
    supervision = _audit_action_object(request, id_supervision)
    if not supervision:
        return HttpResponseForbidden("Permission denied.")
    try:
        supervision_reject(supervision, request.POST.get("rejection_reason"))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Work returned to the contractor for corrections.")
    return _redirect_audit_detail(request, supervision, company_slug)


@require_POST
def supervision_final_audit_view(request, id_supervision, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user, "supervision", PERMISSION_APPROVE
    )
    if permission_response:
        return permission_response
    supervision = _audit_action_object(request, id_supervision)
    if not supervision:
        return HttpResponseForbidden("Permission denied.")
    try:
        supervision_mark_final_audit(supervision)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Final audit approved. The related work is now completed.")
    return _redirect_audit_detail(request, supervision, company_slug)


class SupervisionViewSet(TenantModelViewSet):
    module_name = "supervision"
    queryset = Supervision.objects.all()
    serializer_class = SupervisionSerializer
    tenant_filter_path = None
    tenant_create_field = None

    def get_queryset(self):
        return supervision_list_for_user(self.request.user)

    def perform_create(self, serializer):
        project = serializer.validated_data.get("id_project")
        inspection = serializer.validated_data.get("id_inspection_assignment")
        supervisor = serializer.validated_data.get("id_supervisor")
        company_id = project.id_company_id if project else inspection.id_company_id
        if not self.request.user.is_superuser and company_id != self.request.user.id_company_id:
            raise PermissionDenied("You can only create audits for your company.")
        if supervisor and supervisor.id_company_id != company_id:
            raise PermissionDenied("Supervisor must belong to the audited company.")
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        if not user_can_access_supervision(self.request.user, instance):
            raise PermissionDenied("You can only update audits from your company.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not user_can_module_action(request.user, "supervision", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to approve audits.")
        supervision = self.get_object()
        supervision_approve(supervision)
        return Response(SupervisionSerializer(supervision).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not user_can_module_action(request.user, "supervision", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to reject audits.")
        supervision = self.get_object()
        try:
            supervision_reject(supervision, request.data.get("rejection_reason"))
        except ValueError as exc:
            raise PermissionDenied(str(exc))
        return Response(SupervisionSerializer(supervision).data)

    @action(detail=True, methods=["post"], url_path="final-audit")
    def final_audit(self, request, pk=None):
        if not user_can_module_action(request.user, "supervision", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to complete final audit.")
        supervision = self.get_object()
        try:
            supervision_mark_final_audit(supervision)
        except ValueError as exc:
            raise PermissionDenied(str(exc))
        return Response(SupervisionSerializer(supervision).data)
