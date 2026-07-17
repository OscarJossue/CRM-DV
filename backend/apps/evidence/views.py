from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from urllib.parse import urlencode
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.exceptions import PermissionDenied

from apps.core.dashboard_ui import build_dashboard_items
from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    user_can_module_action,
)
from apps.projects.selectors import project_list_for_user

from .forms import EvidenceFileForm
from .models import EvidenceFile
from .permissions import user_can_access_evidence_file
from .selectors import evidence_file_list_for_user
from .serializers import EvidenceFileSerializer
from .services import evidence_file_create, evidence_file_update


class EvidenceFileListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "evidence"
    permission_required = PERMISSION_VIEW
    template_name = "evidence/list.html"
    context_object_name = "evidence_files"
    paginate_by = 20
    login_url = "/login/"

    evidence_groups = {
        "photos": ["project_photo", "inspection_photo", "before_photo", "after_photo"],
        "documents": ["document", "invoice", "payment"],
        "contracts": ["contract"],
        "other": ["other", ""],
    }

    def get_queryset(self):
        base_queryset = evidence_file_list_for_user(self.request.user)
        self.evidence_base_queryset = base_queryset
        queryset = base_queryset
        query = (self.request.GET.get("q") or "").strip()
        kind = (self.request.GET.get("kind") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(id_project__project_code__icontains=token)
                    | Q(id_project__name__icontains=token)
                    | Q(id_project__id_client__client_code__icontains=token)
                    | Q(id_project__id_client__name__icontains=token)
                    | Q(id_project__id_client__dni__icontains=token)
                    | Q(description__icontains=token)
                    | Q(id_user__email__icontains=token)
                )

        if kind in self.evidence_groups:
            values = self.evidence_groups[kind]
            if kind == "other":
                queryset = queryset.filter(Q(file_type__in=values) | Q(file_type__isnull=True))
            else:
                queryset = queryset.filter(file_type__in=values)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Evidence Files"
        context["can_create_evidence"] = user_can_module_action(self.request.user, "evidence", PERMISSION_CREATE)
        context["can_edit_evidence"] = user_can_module_action(self.request.user, "evidence", PERMISSION_EDIT)

        current_kind = self.request.GET.get("kind", "")
        context["evidence_filters"] = {"q": self.request.GET.get("q", ""), "kind": current_kind}
        base_queryset = getattr(self, "evidence_base_queryset", evidence_file_list_for_user(self.request.user))
        counts = {
            "photos": base_queryset.filter(file_type__in=self.evidence_groups["photos"]).count(),
            "documents": base_queryset.filter(file_type__in=self.evidence_groups["documents"]).count(),
            "contracts": base_queryset.filter(file_type="contract").count(),
            "other": base_queryset.filter(Q(file_type__in=self.evidence_groups["other"]) | Q(file_type__isnull=True)).count(),
        }
        context["evidence_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {"value": "photos", "label": "Photos", "caption": "Project and inspection images", "icon": "bi-images", "color": "#0868e8"},
                {"value": "documents", "label": "Documents", "caption": "Documents, invoices and payments", "icon": "bi-file-earmark-text", "color": "#7c3aed"},
                {"value": "contracts", "label": "Contracts", "caption": "Contract evidence", "icon": "bi-file-earmark-check", "color": "#0e9f6e"},
                {"value": "other", "label": "Other", "caption": "Other uploaded evidence", "icon": "bi-paperclip", "color": "#64748b"},
            ],
            counts,
            active_value=current_kind,
            parameter="kind",
        )
        params = self.request.GET.copy(); params.pop("page", None)
        context["evidence_filter_query"] = urlencode(params, doseq=True)
        return context


class EvidenceFileDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "evidence"
    permission_required = PERMISSION_VIEW
    model = EvidenceFile
    template_name = "evidence/detail.html"
    context_object_name = "evidence_file"
    pk_url_kwarg = "id_file"
    login_url = "/login/"

    def get_queryset(self):
        return evidence_file_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Evidence Details"
        context["can_edit_evidence"] = user_can_module_action(
            self.request.user,
            "evidence",
            PERMISSION_EDIT,
        )
        return context


class EvidenceFileCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "evidence"
    permission_required = PERMISSION_CREATE
    model = EvidenceFile
    form_class = EvidenceFileForm
    template_name = "evidence/form.html"
    success_url = reverse_lazy("evidence:evidence_file_list")
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        id_project = self.kwargs.get("id_project")

        if id_project:
            self.project = get_object_or_404(
                project_list_for_user(request.user),
                id_project=id_project,
            )

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["project"] = self.project
        return kwargs

    def form_valid(self, form):
        project = form.cleaned_data.get("id_project") or self.project

        self.object = evidence_file_create(
            user=self.request.user,
            id_project=project,
            file_type=form.cleaned_data.get("file_type"),
            file_url=form.cleaned_data.get("file_url"),
            description=form.cleaned_data.get("description"),
            file_upload=form.cleaned_data.get("file_upload"),
        )

        messages.success(self.request, "Evidence file created successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "evidence:evidence_file_detail",
            kwargs={"id_file": self.object.id_file},
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the evidence form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Evidence"
        context["form_title"] = "Create Evidence"
        context["submit_label"] = "Save Evidence"
        context["project"] = self.project
        return context


class EvidenceFileUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "evidence"
    permission_required = PERMISSION_EDIT
    model = EvidenceFile
    form_class = EvidenceFileForm
    template_name = "evidence/form.html"
    context_object_name = "evidence_file"
    pk_url_kwarg = "id_file"
    login_url = "/login/"

    def get_queryset(self):
        return evidence_file_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = evidence_file_update(
            self.object,
            id_project=form.cleaned_data.get("id_project"),
            file_type=form.cleaned_data.get("file_type"),
            file_url=form.cleaned_data.get("file_url"),
            description=form.cleaned_data.get("description"),
            file_upload=form.cleaned_data.get("file_upload"),
        )

        messages.success(self.request, "Evidence file updated successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "evidence:evidence_file_detail",
            kwargs={"id_file": self.object.id_file},
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the evidence form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Evidence"
        context["form_title"] = "Edit Evidence"
        context["submit_label"] = "Update Evidence"
        context["project"] = self.object.id_project
        return context


class EvidenceFileViewSet(TenantModelViewSet):
    module_name = "evidence"
    queryset = EvidenceFile.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_user",
    ).all()
    serializer_class = EvidenceFileSerializer
    tenant_filter_path = "id_project__id_company"
    tenant_create_field = None

    def get_queryset(self):
        return evidence_file_list_for_user(self.request.user)

    def perform_create(self, serializer):
        project = serializer.validated_data.get("id_project")

        if not self.request.user.is_superuser:
            if not project or project.id_company_id != self.request.user.id_company_id:
                raise PermissionDenied("You can only create evidence for your company.")

        serializer.save(id_user=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()

        if not user_can_access_evidence_file(self.request.user, instance):
            raise PermissionDenied("You can only update evidence from your company.")

        serializer.save()
