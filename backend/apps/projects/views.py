from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.deletion import ProtectedError
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.urls import NoReverseMatch, reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from apps.opportunities.models import Lead
from apps.accounts.contractor_access import user_is_contractor_only
from apps.core.dashboard_ui import build_dashboard_items
from apps.core.field_photos import collect_photo_slots
from apps.opportunities.models.choices import OPPORTUNITY_STATUS_CONVERTED
from apps.inspections.models import InspectionAssignment
from apps.smtp_settings.services import send_company_email
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from apps.core.pdf import simple_pdf_response

from .models.choices import (
    PROJECT_MANUAL_STATUS_VALUES,
    PROJECT_STATUS_CHOICES,
)

from rest_framework.exceptions import PermissionDenied

from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    user_can_module_action,
)

from .forms import (
    ProjectForm,
    ProjectNoteForm,
)
from .models import (
    Project,
    ProjectAssignment,
    ProjectEvidence,
    ProjectGalleryImage,
    ProjectNote,
)
from .selectors import assignment_list_for_user, project_list_for_user
from .serializers import ProjectSerializer
from .services import (
    approve_project,
    cancel_project,
    close_project,
    project_has_field_submission,
    project_submission_requirements,
    request_project_corrections,
    submit_project_for_review,
    user_can_review_project,
    user_can_submit_project_work,
    user_is_assigned_to_project,
)


PROJECT_STATUS_STAGES = [
    ("draft", "Draft", "bi-pencil-square", "#9ca3af", "is-neutral"),
    ("pending", "Pending", "bi-hourglass-split", "#0868e8", "is-blue"),
    ("in_progress", "In Progress", "bi-tools", "#f59e0b", "is-warning"),
    ("review", "Under Review", "bi-eye", "#7c3aed", "is-violet"),
    ("completed", "Closed", "bi-check2-circle", "#0e9f6e", "is-success"),
    ("cancelled", "Cancelled", "bi-x-lg", "#6b7280", "is-void"),
]
PROJECT_STATUS_CAPTION_CLASSES = {stage[0]: stage[4] for stage in PROJECT_STATUS_STAGES}


def reverse_project_url(request, view_name, *, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    if slug:
        try:
            return reverse(
                f"company_projects:{view_name}",
                kwargs={"company_slug": slug, **kwargs},
            )
        except NoReverseMatch:
            pass
    return reverse(f"projects:{view_name}", kwargs=kwargs)






def reverse_contractor_portal_url(request, view_name, *, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    if slug:
        try:
            return reverse(
                f"company_contractor_portal:{view_name}",
                kwargs={"company_slug": slug, **kwargs},
            )
        except NoReverseMatch:
            pass
    return reverse(f"contractor_portal:{view_name}", kwargs=kwargs)

def reverse_project_companion_invoice_create_url(request, id_project, *, company_slug=None):
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    if slug:
        try:
            return reverse(
                "company_invoices:invoice_create_for_project",
                kwargs={"company_slug": slug, "id_project": id_project},
            )
        except NoReverseMatch:
            pass
    return reverse("invoices:invoice_create_for_project", kwargs={"id_project": id_project})

def request_wants_json(request):
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def project_queryset_with_submission(queryset):
    return queryset.annotate(
        has_field_evidence=(
            Exists(
                ProjectEvidence.objects.filter(id_project_id=OuterRef("pk")).exclude(file="")
            )
            | Exists(
                ProjectGalleryImage.objects.filter(project_id=OuterRef("pk")).exclude(image="")
            )
        )
    )


def user_can_change_project_status(user, project):
    if user_is_contractor_only(user):
        return user_is_assigned_to_project(user, project)
    if user_can_module_action(user, "projects", PERMISSION_EDIT) or user_can_module_action(
        user, "projects", PERMISSION_APPROVE
    ):
        return True
    if project.id_inspector_id == getattr(user, "pk", None):
        return True
    return ProjectAssignment.objects.filter(id_project=project, id_user=user).exists()


class ProjectListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "projects"
    permission_required = PERMISSION_VIEW
    template_name = "projects/list.html"
    context_object_name = "projects"
    paginate_by = 20
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if user_is_contractor_only(request.user):
            return redirect(
                reverse_contractor_portal_url(
                    request,
                    "project_list",
                    company_slug=kwargs.get("company_slug"),
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        base_queryset = project_queryset_with_submission(project_list_for_user(self.request.user))
        due_ids = base_queryset.filter(
            status="pending", start_date__lte=timezone.localdate()
        ).values_list("id_project", flat=True)
        Project.objects.filter(id_project__in=due_ids).update(status="in_progress")
        base_queryset = project_queryset_with_submission(project_list_for_user(self.request.user))
        self.project_base_queryset = base_queryset
        queryset = base_queryset
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(project_code__icontains=token)
                    | Q(name__icontains=token)
                    | Q(id_client__client_code__icontains=token)
                    | Q(id_client__name__icontains=token)
                    | Q(id_client__dni__icontains=token)
                    | Q(id_inspector__email__icontains=token)
                )

        valid_statuses = {value for value, _label in PROJECT_STATUS_CHOICES}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company_slug = self.kwargs.get("company_slug")
        context["page_title"] = "Projects"
        context["can_create_projects"] = user_can_module_action(user, "projects", PERMISSION_CREATE)
        context["can_edit_projects"] = user_can_module_action(user, "projects", PERMISSION_EDIT)
        context["can_approve_projects"] = user_can_module_action(user, "projects", PERMISSION_APPROVE)
        context["project_status_stages"] = PROJECT_STATUS_STAGES
        context["project_list_url"] = reverse_project_url(
            self.request, "project_list", company_slug=company_slug
        )
        context["project_create_url"] = reverse_project_url(
            self.request, "project_create", company_slug=company_slug
        )

        projects = list(context.get("projects", []))
        can_manage_status = context["can_edit_projects"] or context["can_approve_projects"]
        assigned_ids = set()
        if projects and not can_manage_status:
            assigned_ids = set(
                ProjectAssignment.objects.filter(
                    id_user=user,
                    id_project_id__in=[project.id_project for project in projects],
                ).values_list("id_project_id", flat=True)
            )

        status_labels = {
            "draft": "Draft",
            "pending": "Pending",
            "in_progress": "In Progress",
            "review": "Under Review",
            "completed": "Closed",
            "cancelled": "Cancelled",
        }
        for project in projects:
            project.status_label = status_labels.get(
                project.status, project.status.replace("_", " ").title()
            )
            project.status_caption_class = PROJECT_STATUS_CAPTION_CLASSES.get(project.status, "is-neutral")
            project.can_change_status = (
                project.status in PROJECT_MANUAL_STATUS_VALUES
                and (
                    can_manage_status
                    or project.id_inspector_id == user.pk
                    or project.id_project in assigned_ids
                )
            )
            project.allowed_statuses = []
            project.has_field_submission = project_has_field_submission(project)
            project.can_delete_record = (
                context["can_edit_projects"]
                and project.status in PROJECT_MANUAL_STATUS_VALUES
                and not project.has_field_submission
            )
            project.can_cancel_record = (
                context["can_approve_projects"]
                and project.has_field_submission
                and project.status not in {"completed", "cancelled"}
            )
            project.can_close_record = (
                context["can_approve_projects"]
                and project.status not in {"completed", "cancelled"}
            )
            project.detail_url = reverse_project_url(
                self.request, "project_detail", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
            project.edit_url = reverse_project_url(
                self.request, "project_update", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
            project.delete_url = reverse_project_url(
                self.request, "project_delete", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
            project.cancel_url = reverse_project_url(
                self.request, "project_cancel", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
            project.close_url = reverse_project_url(
                self.request, "project_close", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
            project.status_update_url = reverse_project_url(
                self.request, "project_status_update", company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )

        current_status = self.request.GET.get("status", "")
        context["project_filters"] = {"q": self.request.GET.get("q", ""), "status": current_status}
        base_queryset = getattr(self, "project_base_queryset", project_list_for_user(user))
        counts = {row["status"]: row["total"] for row in base_queryset.values("status").annotate(total=Count("id_project"))}
        context["project_total_count"] = base_queryset.count()
        context["project_total_value"] = base_queryset.aggregate(total=Sum("contract_amount"))["total"] or 0
        context["project_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {"value": "draft", "label": "Draft", "caption": "Editable draft", "icon": "bi-pencil-square", "color": "#9ca3af"},
                {"value": "pending", "label": "Pending", "caption": "Waiting for start date", "icon": "bi-hourglass-split", "color": "#0868e8"},
                {"value": "in_progress", "label": "In Progress", "caption": "Field work active", "icon": "bi-tools", "color": "#f59e0b"},
                {"value": "review", "label": "Under Review", "caption": "Evidence awaiting approval", "icon": "bi-eye", "color": "#7c3aed"},
                {"value": "completed", "label": "Closed", "caption": "Approved and closed", "icon": "bi-check2-circle", "color": "#0e9f6e"},
                {"value": "cancelled", "label": "Cancelled", "caption": "Frozen with reason", "icon": "bi-x-circle", "color": "#6b7280"},
            ],
            counts,
            active_value=current_status,
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        context["project_filter_query"] = urlencode(params, doseq=True)
        return context


class ProjectDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "projects"
    permission_required = PERMISSION_VIEW
    model = Project
    template_name = "projects/detail.html"
    context_object_name = "project"
    pk_url_kwarg = "id_project"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if user_is_contractor_only(request.user):
            return redirect(
                reverse_contractor_portal_url(
                    request,
                    "project_detail",
                    company_slug=kwargs.get("company_slug"),
                    kwargs={"id_project": kwargs.get("id_project")},
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return project_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_slug = self.kwargs.get("company_slug")

        context["page_title"] = self.object.name
        if (
            self.object.status == "pending"
            and self.object.start_date
            and self.object.start_date <= timezone.localdate()
        ):
            self.object.status = "in_progress"
            self.object.save(update_fields=["status", "updated_at"])

        context["project_evidence"] = list(
            self.object.evidence.select_related("uploaded_by")
            .exclude(file="")
            .order_by("uploaded_at", "id_project_evidence")
        )

        context["can_edit_projects"] = user_can_module_action(
            self.request.user, "projects", PERMISSION_EDIT
        )
        context["can_approve_projects"] = user_can_module_action(
            self.request.user, "projects", PERMISSION_APPROVE
        )
        context["user_is_project_assigned"] = ProjectAssignment.objects.filter(
            id_project=self.object, id_user=self.request.user
        ).exists()
        context["user_is_project_inspector"] = self.object.id_inspector_id == self.request.user.pk
        context["can_submit_project_work"] = user_can_submit_project_work(
            self.request.user, self.object
        ) and self.object.status in PROJECT_MANUAL_STATUS_VALUES
        context["submission_requirements"] = (
            project_submission_requirements(self.object, self.request.user)
            if context["can_submit_project_work"] else None
        )
        context["can_review_project"] = (
            self.object.status == "review"
            and user_can_review_project(self.request.user, self.object)
        )
        context["has_field_submission"] = project_has_field_submission(self.object)
        context["can_delete_project"] = (
            context["can_edit_projects"]
            and self.object.status in PROJECT_MANUAL_STATUS_VALUES
            and not context["has_field_submission"]
        )
        context["can_cancel_project"] = (
            context["has_field_submission"]
            and self.object.status not in {"completed", "cancelled"}
            and user_can_review_project(self.request.user, self.object)
        )
        context["can_close_project"] = (
            self.object.status not in {"completed", "cancelled"}
            and user_can_review_project(self.request.user, self.object)
        )
        context["can_view_project_pdf"] = self.object.status in {"completed", "cancelled"}
        context["is_project_locked"] = self.object.status in {"review", "completed", "cancelled"}
        context["project_status_label"] = {
            "draft": "Draft",
            "pending": "Pending",
            "in_progress": "In Progress",
            "review": "Under Review",
            "completed": "Closed",
            "cancelled": "Cancelled",
        }.get(self.object.status, self.object.status.replace("_", " ").title())
        self.object.status_label = context["project_status_label"]
        context["can_change_project_status"] = False
        context["project_status_stages"] = PROJECT_STATUS_STAGES
        self.object.can_change_status = context["can_change_project_status"]
        self.object.allowed_statuses = []
        self.object.can_close_record = context["can_close_project"]
        self.object.status_caption_class = PROJECT_STATUS_CAPTION_CLASSES.get(
            self.object.status, "is-neutral"
        )
        self.object.status_update_url = reverse_project_url(
            self.request, "project_status_update", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )

        context["note_form"] = ProjectNoteForm()
        context["project_notes"] = ProjectNote.objects.select_related("created_by").filter(
            id_project=self.object
        ).order_by("-created_at")

        show_invoice_popup_project_id = self.request.session.pop(
            "show_invoice_popup_project_id", None
        )
        context["show_invoice_popup"] = (
            show_invoice_popup_project_id == self.object.id_project
            and self.object.invoice_status == "no_invoice"
        )
        context["project_invoice_create_url"] = reverse_project_companion_invoice_create_url(
            self.request, self.object.id_project, company_slug=company_slug
        )
        context["project_list_url"] = reverse_project_url(
            self.request, "project_list", company_slug=company_slug
        )
        context["project_update_url"] = reverse_project_url(
            self.request, "project_update", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_delete_url"] = reverse_project_url(
            self.request, "project_delete", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_submit_review_url"] = reverse_project_url(
            self.request, "project_submit_review", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_approve_url"] = reverse_project_url(
            self.request, "project_approve", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_corrections_url"] = reverse_project_url(
            self.request, "project_request_corrections", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_cancel_url"] = reverse_project_url(
            self.request, "project_cancel", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_close_url"] = reverse_project_url(
            self.request, "project_close", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        self.object.close_url = context["project_close_url"]
        context["project_pdf_url"] = reverse_project_url(
            self.request, "project_pdf", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_note_create_url"] = reverse_project_url(
            self.request, "project_note_create", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )
        context["project_contractor_update_url"] = reverse_project_url(
            self.request, "project_contractor_update", company_slug=company_slug,
            kwargs={"id_project": self.object.id_project},
        )

        return context


class ProjectCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "projects"
    permission_required = PERMISSION_CREATE
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"
    login_url = "/login/"

    def get_opportunity(self):
        opportunity_id = (
            self.request.GET.get("opportunity_id")
            or self.request.POST.get("opportunity_id")
        )

        if not opportunity_id:
            return None

        return (
            Lead.objects
            .select_related("id_client", "id_company", "id_assigned_user")
            .filter(
                id_lead=opportunity_id,
                id_company_id=self.request.user.id_company_id,
            )
            .first()
        )

    def get_inspection(self):
        assignment_id = self.kwargs.get("id_assignment")
        if not assignment_id:
            return None
        queryset = InspectionAssignment.objects.select_related(
            "client", "client__id_company", "inspector", "id_project"
        )
        if not self.request.user.is_superuser:
            queryset = queryset.filter(client__id_company_id=self.request.user.id_company_id)
        return get_object_or_404(
            queryset,
            id_assignment=assignment_id,
            status="completed",
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["opportunity"] = self.get_opportunity()
        kwargs["inspection"] = self.get_inspection()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        inspection = self.get_inspection()
        if inspection:
            client = inspection.client
            initial.update(
                {
                    "id_client": client.id_client,
                    "id_inspector": inspection.inspector_id,
                    "name": f"Project - {client.name or 'Inspection'}",
                    "project_address": client.address or "",
                    "google_maps_url": inspection.google_maps_url or "",
                    "description": "\n\n".join(
                        value for value in [inspection.notes, inspection.inspection_notes] if value
                    ),
                    "project_notes": inspection.recommendations or "",
                }
            )
            return initial

        opportunity = self.get_opportunity()

        if not opportunity:
            return initial

        client = getattr(opportunity, "id_client", None)

        if client:
            initial["id_client"] = client.id_client
            initial["project_address"] = getattr(client, "address", "") or ""

            client_name = (
                getattr(client, "full_name", "")
                or getattr(client, "name", "")
                or str(client)
            )

            initial["name"] = (
                getattr(opportunity, "opportunity_name", "")
                or getattr(opportunity, "title", "")
                or getattr(opportunity, "name", "")
                or getattr(opportunity, "opportunity_description", "")
                or f"Project - {client_name}"
            )

        initial["contract_amount"] = getattr(opportunity, "approximate_value", None) or 0

        initial["description"] = (
            getattr(opportunity, "description", "")
            or getattr(opportunity, "opportunity_description", "")
            or ""
        )

        initial["project_notes"] = getattr(opportunity, "notes", "") or ""

        return initial
    def get_success_url(self):
        return reverse_project_url(
            self.request,
            "project_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_project": self.object.id_project},
        )

    def form_valid(self, form):
        opportunity = self.get_opportunity()
        inspection = self.get_inspection()
        if inspection and inspection.id_project_id:
            messages.info(self.request, "This inspection is already linked to a project.")
            return redirect(
                reverse_project_url(
                    self.request,
                    "project_detail",
                    company_slug=self.kwargs.get("company_slug"),
                    kwargs={"id_project": inspection.id_project_id},
                )
            )

        form.instance.status = (
            "draft" if self.request.POST.get("save_mode") == "draft" else "pending"
        )
        self.object = form.save()

        if inspection:
            inspection.id_project = self.object
            inspection.save(update_fields=["id_project", "updated_at"])

        if opportunity:
            opportunity.status = OPPORTUNITY_STATUS_CONVERTED
            opportunity.id_converted_project = self.object
            opportunity.save(update_fields=["status", "id_converted_project", "updated_at"])

        if (
            self.object.status == "pending"
            and self.object.id_inspector
            and self.object.id_inspector.email
        ):
            try:
                supervisor = self.object.id_inspector
                full_name = (
                    f"{supervisor.first_name or ''} {supervisor.last_name or ''}".strip()
                    or supervisor.email
                )
                send_company_email(
                    company=self.object.id_company,
                    subject="New Project Assignment",
                    text_body=(
                        f"Hello {full_name},\n\n"
                        "You have been assigned as supervisor / inspector.\n\n"
                        f"Project: {self.object.name}\n"
                        f"Address: {self.object.project_address or 'N/A'}\n"
                        f"Start date: {self.object.start_date or 'N/A'}\n"
                    ),
                    to_emails=[supervisor.email],
                    html_body=None,
                )
            except Exception as error:
                messages.warning(
                    self.request,
                    f"Project created, but the supervisor email could not be sent: {error}",
                )

        if self.object.status == "draft":
            messages.success(self.request, "Project saved as draft.")
        else:
            messages.success(self.request, "Project created and set to Pending.")
            self.request.session["show_invoice_popup_project_id"] = self.object.id_project
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the project form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        opportunity = self.get_opportunity()
        inspection = self.get_inspection()

        if inspection:
            context["page_title"] = "Create Project From Inspection"
            context["form_title"] = "Create Project From Inspection"
        elif opportunity:
            context["page_title"] = "Create Project From Opportunity"
            context["form_title"] = "Create Project From Opportunity"
        else:
            context["page_title"] = "Create Project"
            context["form_title"] = "Create Project"

        context["submit_label"] = "Save Project"
        context["allow_save_draft"] = True
        context["primary_submit_label"] = "Save and set Pending"
        context["opportunity"] = opportunity
        context["inspection"] = inspection
        context["cancel_url"] = reverse_project_url(
            self.request, "project_list", company_slug=self.kwargs.get("company_slug")
        )

        return context


class ProjectUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "projects"
    permission_required = PERMISSION_EDIT
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"
    context_object_name = "project"
    pk_url_kwarg = "id_project"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status in {"review", "completed", "cancelled"}:
            messages.error(request, "This project is locked. Use the review or cancellation actions.")
            return redirect(reverse_project_url(request, "project_detail", company_slug=kwargs.get("company_slug"), kwargs={"id_project": self.object.id_project}))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return project_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["opportunity"] = None
        return kwargs

    def get_success_url(self):
        return reverse_project_url(
            self.request,
            "project_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_project": self.object.id_project},
        )

    def form_valid(self, form):
        previous_status = self.object.status
        if previous_status == "draft":
            form.instance.status = (
                "draft" if self.request.POST.get("save_mode") == "draft" else "pending"
            )
        else:
            form.instance.status = previous_status
        self.object = form.save()
        messages.success(
            self.request,
            "Project saved as draft."
            if self.object.status == "draft"
            else "Project updated successfully.",
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the project form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Edit Project"
        context["form_title"] = "Edit Project"
        context["submit_label"] = "Update Project"
        context["allow_save_draft"] = self.object.status == "draft"
        context["primary_submit_label"] = (
            "Save and set Pending" if self.object.status == "draft" else "Save changes"
        )
        context["cancel_url"] = reverse_project_url(
            self.request, "project_detail", company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_project": self.object.id_project},
        )

        return context


class ProjectDeleteView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "projects"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def get_project(self):
        return get_object_or_404(
            project_list_for_user(self.request.user),
            id_project=self.kwargs.get("id_project"),
        )

    def get(self, request, *args, **kwargs):
        project = self.get_project()
        messages.info(request, "Use the project action window to confirm deletion.")
        return redirect(
            reverse_project_url(
                request,
                "project_detail",
                company_slug=kwargs.get("company_slug"),
                kwargs={"id_project": project.id_project},
            )
        )

    def post(self, request, *args, **kwargs):
        project = self.get_project()
        detail_url = reverse_project_url(
            request,
            "project_detail",
            company_slug=kwargs.get("company_slug"),
            kwargs={"id_project": project.id_project},
        )
        if project_has_field_submission(project):
            messages.error(
                request,
                "This project already received contractor evidence and cannot be deleted. Cancel it with a reason instead.",
            )
            return redirect(detail_url)

        try:
            has_invoices = project.invoices.exists()
        except Exception:
            has_invoices = False
        if has_invoices:
            messages.error(request, "This project has invoices and cannot be deleted.")
            return redirect(detail_url)

        try:
            project.delete()
        except ProtectedError:
            messages.error(
                request,
                "This project is linked to a protected record and cannot be deleted.",
            )
            return redirect(detail_url)

        messages.success(request, "Project deleted successfully.")
        return redirect(
            reverse_project_url(
                request,
                "project_list",
                company_slug=kwargs.get("company_slug"),
            )
        )


class ProjectAssignmentCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    """Compatibility redirect for the removed assigned-users interface."""

    module_name = "projects"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def _redirect(self, request, *args, **kwargs):
        project = get_object_or_404(
            project_list_for_user(request.user),
            id_project=kwargs.get("id_project"),
        )
        messages.info(
            request,
            "Assigned users were removed. Use the Supervisor / Inspector field on the project instead.",
        )
        return redirect(
            reverse_project_url(
                request,
                "project_detail",
                company_slug=kwargs.get("company_slug"),
                kwargs={"id_project": project.id_project},
            )
        )

    get = _redirect
    post = _redirect


class ProjectAssignmentUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    """Compatibility redirect for old assignment edit links."""

    module_name = "projects"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def _redirect(self, request, *args, **kwargs):
        assignment = get_object_or_404(
            assignment_list_for_user(request.user),
            id_assignment=kwargs.get("id_assignment"),
        )
        messages.info(
            request,
            "Assigned users were removed. Use the Supervisor / Inspector field on the project instead.",
        )
        return redirect(
            reverse_project_url(
                request,
                "project_detail",
                company_slug=kwargs.get("company_slug"),
                kwargs={"id_project": assignment.id_project_id},
            )
        )

    get = _redirect
    post = _redirect


@require_POST
def project_contractor_update_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    if not user_can_submit_project_work(request.user, project):
        return HttpResponseForbidden("You cannot update this project delivery.")
    if project.status not in PROJECT_MANUAL_STATUS_VALUES:
        return HttpResponseForbidden("This project is locked and cannot be edited.")
    project.contractor_observations = (request.POST.get("contractor_observations") or "").strip()
    project.contractor_recommendations = (request.POST.get("contractor_recommendations") or "").strip()
    project.updated_by = request.user
    fields = ["contractor_observations", "contractor_recommendations", "updated_by", "updated_at"]
    if project.status in {"draft", "pending"}:
        project.status = "in_progress"
        fields.append("status")
    project.save(update_fields=fields)
    messages.success(request, "Observations and recommendations saved.")
    return redirect(reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project}) + "#field-notes")


def project_note_create_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    detail_url = reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project})
    if request.method != "POST":
        return redirect(detail_url)
    can_add_note = user_can_module_action(request.user, "projects", PERMISSION_EDIT) or user_can_submit_project_work(request.user, project)
    if not can_add_note or project.status not in PROJECT_MANUAL_STATUS_VALUES:
        return HttpResponseForbidden("You cannot add notes to this project.")
    note_text = request.POST.get("note", "").strip()
    if not note_text:
        messages.error(request, "Please write a project note before saving.")
        return redirect(detail_url)
    ProjectNote.objects.create(id_project=project, created_by=request.user, note=note_text)
    messages.success(request, "Project note added successfully.")
    return redirect(detail_url)


@require_POST
def project_status_update_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    message = (
        "Project status is automatic. Use Save Draft, Save Pending, contractor submission, "
        "review, approval/closure or cancellation actions."
    )
    if request_wants_json(request):
        return JsonResponse(
            {"ok": False, "status": project.status, "message": message}, status=400
        )
    messages.error(request, message)
    return redirect(
        reverse_project_url(
            request,
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": project.id_project},
        )
    )


@require_POST
def project_submit_for_review_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    try:
        submit_project_for_review(project, request.user, observations=request.POST.get("contractor_observations"), recommendations=request.POST.get("contractor_recommendations"), uploads=collect_photo_slots(request))
        messages.success(request, "Project evidence was saved as WebP and sent for review.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project}))

project_submit_for_audit_view = project_submit_for_review_view


@require_POST
def project_close_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    try:
        close_project(project, request.user)
        messages.success(
            request,
            "Project closed successfully. Progress is 100% and the finalization date was set automatically.",
        )
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(
        reverse_project_url(
            request,
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": project.id_project},
        )
    )


@require_POST
def project_approve_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    try:
        approve_project(project, request.user)
        messages.success(request, "Project approved and closed. The finalization date was set automatically.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project}))


@require_POST
def project_request_corrections_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    try:
        request_project_corrections(project, request.user, request.POST.get("correction_reason"))
        messages.success(request, "Corrections requested. The project returned to In Progress.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project}))


@require_POST
def project_cancel_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    try:
        cancel_project(project, request.user, request.POST.get("cancel_reason") or request.POST.get("void_reason"))
        messages.success(request, "Project cancelled and frozen successfully.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_project_url(request, "project_detail", company_slug=company_slug, kwargs={"id_project": project.id_project}))


def project_pdf_view(request, id_project, company_slug=None):
    project = get_object_or_404(project_list_for_user(request.user), id_project=id_project)
    if project.status not in {"completed", "cancelled"}:
        return HttpResponseForbidden("The project PDF is available after approval.")
    lines = [
        f"Code: {project.project_code or project.id_project}",
        f"Client: {project.id_client.name}",
        f"Status: {project.get_status_display()}",
        f"Address: {project.project_address or project.id_client.address or '-'}",
        f"Start date: {project.start_date or '-'}",
        f"End date: {project.end_date or '-'}",
        f"Contract amount: {project.contract_amount}",
        f"Description: {project.description or '-'}",
        f"Observations: {project.contractor_observations or '-'}",
        f"Recommendations: {project.contractor_recommendations or '-'}",
    ]
    if project.cancellation_reason:
        lines.append(f"Void reason: {project.cancellation_reason}")
    return simple_pdf_response(project.name, lines, filename=f"project-{project.project_code or project.id_project}.pdf")


class ProjectViewSet(TenantModelViewSet):
    module_name = "projects"
    queryset = Project.objects.select_related(
        "id_company",
        "id_client",
        "id_inspector",
        "id_opportunity",
    ).all()
    serializer_class = ProjectSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return project_list_for_user(self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        serializer.save(
            id_company=self.request.user.pk_company,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()

        if instance.id_company_id != self.request.user.id_company_id:
            raise PermissionDenied("You can only update projects from your company.")

        serializer.save(
            id_company=self.request.user.pk_company,
            updated_by=self.request.user,
        )

