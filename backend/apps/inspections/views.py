from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef, Q
from urllib.parse import urlencode
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from apps.core.dashboard_ui import build_dashboard_items
from apps.core.field_photos import collect_photo_slots
from apps.core.mixins import TenantModelViewSet
from apps.smtp_settings.services import send_company_email
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)
from apps.accounts.contractor_access import user_is_contractor_only

from .forms import InspectionAssignmentForm
from .models.choices import (
    INSPECTION_ASSIGNMENT_STATUS_CHOICES,
    INSPECTION_MANUAL_STATUS_VALUES,
)
from .models import (
    Inspection,
    InspectionAssignment,
    InspectionAssignmentGalleryImage,
)

from .selectors import inspection_list_for_user
from .serializers import InspectionSerializer
from .services import (
    approve_inspection_assignment,
    cancel_inspection,
    close_inspection,
    inspection_has_field_submission,
    inspection_approve,
    inspection_assignment_submission_requirements,
    request_inspection_corrections,
    submit_inspection_assignment_for_review,
    user_can_review_inspection,
    user_can_submit_inspection_work,
)


INSPECTION_STATUS_STAGES = [
    ("draft", "Draft", "bi-pencil-square", "#9ca3af", "is-neutral"),
    ("pending", "Pending", "bi-hourglass-split", "#0868e8", "is-blue"),
    ("in_progress", "In Progress", "bi-tools", "#f59e0b", "is-warning"),
    ("review", "Under Review", "bi-eye", "#7c3aed", "is-violet"),
    ("completed", "Closed", "bi-check2-circle", "#0e9f6e", "is-success"),
    ("cancelled", "Cancelled", "bi-x-lg", "#6b7280", "is-void"),
]
INSPECTION_STATUS_CAPTION_CLASSES = {stage[0]: stage[4] for stage in INSPECTION_STATUS_STAGES}


def reverse_inspection_url(request, view_name, *, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    if slug:
        try:
            return reverse(
                f"company_inspections:{view_name}",
                kwargs={"company_slug": slug, **kwargs},
            )
        except NoReverseMatch:
            pass
    return reverse(f"inspections:{view_name}", kwargs=kwargs)




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

def reverse_estimate_from_inspection_url(request, assignment, company_slug=None):
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    kwargs = {"id_assignment": assignment.id_assignment}
    if slug:
        try:
            return reverse(
                "company_estimates:estimate_create_from_inspection",
                kwargs={"company_slug": slug, **kwargs},
            )
        except NoReverseMatch:
            pass
    return reverse("estimates:estimate_create_from_inspection", kwargs=kwargs)


def reverse_project_from_inspection_url(request, assignment, company_slug=None):
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")
    kwargs = {"id_assignment": assignment.id_assignment}
    if slug:
        try:
            return reverse(
                "company_projects:project_create_from_inspection",
                kwargs={"company_slug": slug, **kwargs},
            )
        except NoReverseMatch:
            pass
    return reverse("projects:project_create_from_inspection", kwargs=kwargs)


def inspection_request_wants_json(request):
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def inspection_queryset_with_submission(queryset):
    return queryset.annotate(
        has_field_evidence=Exists(
            InspectionAssignmentGalleryImage.objects.filter(
                assignment_id=OuterRef("pk")
            ).exclude(file="")
        )
    )


def user_can_manage_all_inspection_assignments(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user_can_module_action(
        user,
        "inspections",
        PERMISSION_EDIT,
    ) or user_can_module_action(
        user,
        "inspections",
        PERMISSION_APPROVE,
    )


def inspection_assignment_queryset_for_user(user):
    queryset = InspectionAssignment.objects.select_related(
        "client",
        "client__id_company",
        "inspector",
        "inspector__id_company",
        "inspector__id_role",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    if not user.id_company_id:
        return queryset.none()

    queryset = queryset.filter(
        client__id_company_id=user.id_company_id,
    )

    if user_can_manage_all_inspection_assignments(user):
        return queryset

    return queryset.filter(
        inspector=user,
    )
class InspectionAssignmentListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "inspections"
    permission_required = PERMISSION_VIEW
    model = InspectionAssignment
    template_name = "inspections/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 20
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if user_is_contractor_only(request.user):
            return redirect(
                reverse_contractor_portal_url(
                    request,
                    "inspection_list",
                    company_slug=kwargs.get("company_slug"),
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        base_queryset = inspection_queryset_with_submission(
            inspection_assignment_queryset_for_user(self.request.user)
        ).order_by("-inspection_date", "-created_at")
        due_ids = base_queryset.filter(
            status="pending", inspection_date__date__lte=timezone.localdate()
        ).values_list("id_assignment", flat=True)
        InspectionAssignment.objects.filter(id_assignment__in=due_ids).update(status="in_progress")
        base_queryset = inspection_queryset_with_submission(
            inspection_assignment_queryset_for_user(self.request.user)
        ).order_by("-inspection_date", "-created_at")
        self.assignment_base_queryset = base_queryset
        queryset = base_queryset
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if query:
            search_filter = (
                Q(client__client_code__icontains=query)
                | Q(client__name__icontains=query)
                | Q(client__dni__icontains=query)
                | Q(inspector__email__icontains=query)
                | Q(notes__icontains=query)
                | Q(inspection_notes__icontains=query)
            )
            if query.isdigit():
                search_filter |= Q(id_assignment=int(query))
            queryset = queryset.filter(search_filter)

        valid_statuses = {value for value, _label in INSPECTION_ASSIGNMENT_STATUS_CHOICES}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company_slug = self.kwargs.get("company_slug")
        context["page_title"] = "Inspections"
        context["can_create_inspections"] = user_can_module_action(user, "inspections", PERMISSION_CREATE)
        context["can_edit_inspections"] = user_can_manage_all_inspection_assignments(user)
        context["inspection_status_stages"] = INSPECTION_STATUS_STAGES
        context["inspection_list_url"] = reverse_inspection_url(
            self.request, "inspection_list", company_slug=company_slug
        )
        context["inspection_create_url"] = reverse_inspection_url(
            self.request, "inspection_create", company_slug=company_slug
        )

        assignments = list(context.get("assignments", []))
        status_labels = {
            "draft": "Draft",
            "pending": "Pending",
            "in_progress": "In Progress",
            "review": "Under Review",
            "completed": "Closed",
            "cancelled": "Cancelled",
        }
        for assignment in assignments:
            assignment.status_label = status_labels.get(
                assignment.status, assignment.status.replace("_", " ").title()
            )
            assignment.status_caption_class = INSPECTION_STATUS_CAPTION_CLASSES.get(
                assignment.status, "is-neutral"
            )
            assignment.can_change_status = False
            assignment.allowed_statuses = []
            assignment.has_field_submission = inspection_has_field_submission(assignment)
            can_review_assignment = user_can_review_inspection(user, assignment)
            assignment.can_delete_record = (
                context["can_edit_inspections"]
                and assignment.status in INSPECTION_MANUAL_STATUS_VALUES
                and not assignment.has_field_submission
            )
            assignment.can_cancel_record = (
                assignment.has_field_submission
                and assignment.status not in {"completed", "cancelled"}
                and can_review_assignment
            )
            assignment.can_close_record = (
                assignment.status not in {"completed", "cancelled"}
                and can_review_assignment
            )
            assignment.can_prepare_project = (
                not assignment.id_project_id
                and user_can_module_action(user, "projects", PERMISSION_CREATE)
            )
            assignment.can_open_completion_options = (
                assignment.can_close_record or assignment.can_prepare_project
            )
            assignment.detail_url = reverse_inspection_url(
                self.request, "inspection_detail", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
            assignment.edit_url = reverse_inspection_url(
                self.request, "inspection_update", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
            assignment.delete_url = reverse_inspection_url(
                self.request, "inspection_delete", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
            assignment.cancel_url = reverse_inspection_url(
                self.request, "inspection_cancel", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
            assignment.close_url = reverse_inspection_url(
                self.request, "inspection_close", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
            assignment.create_project_url = (
                reverse_project_from_inspection_url(
                    self.request, assignment, company_slug=company_slug
                )
                if assignment.status == "completed" and assignment.can_prepare_project
                else ""
            )
            assignment.status_update_url = reverse_inspection_url(
                self.request, "inspection_status_update", company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )

        current_status = self.request.GET.get("status", "")
        context["inspection_filters"] = {"q": self.request.GET.get("q", ""), "status": current_status}
        base_queryset = getattr(self, "assignment_base_queryset", inspection_assignment_queryset_for_user(user))
        counts = {row["status"]: row["total"] for row in base_queryset.values("status").annotate(total=Count("id_assignment"))}
        context["inspection_total_count"] = base_queryset.count()
        context["inspection_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {"value": "draft", "label": "Draft", "caption": "Editable draft", "icon": "bi-pencil-square", "color": "#9ca3af"},
                {"value": "pending", "label": "Pending", "caption": "Waiting for inspection day", "icon": "bi-hourglass-split", "color": "#0868e8"},
                {"value": "in_progress", "label": "In Progress", "caption": "Field work active", "icon": "bi-tools", "color": "#f59e0b"},
                {"value": "review", "label": "Under Review", "caption": "Evidence awaiting approval", "icon": "bi-eye", "color": "#7c3aed"},
                {"value": "completed", "label": "Closed", "caption": "Inspection closed", "icon": "bi-check2-circle", "color": "#0e9f6e"},
                {"value": "cancelled", "label": "Cancelled", "caption": "Frozen with reason", "icon": "bi-x-circle", "color": "#6b7280"},
            ],
            counts,
            active_value=current_status,
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        context["inspection_filter_query"] = urlencode(params, doseq=True)
        return context


class InspectionAssignmentDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "inspections"
    permission_required = PERMISSION_VIEW
    model = InspectionAssignment
    template_name = "inspections/assignment_detail.html"
    context_object_name = "assignment"
    pk_url_kwarg = "id_assignment"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if user_is_contractor_only(request.user):
            return redirect(
                reverse_contractor_portal_url(
                    request,
                    "inspection_detail",
                    company_slug=kwargs.get("company_slug"),
                    kwargs={"id_assignment": kwargs.get("id_assignment")},
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return inspection_assignment_queryset_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_slug = self.kwargs.get("company_slug")

        context["page_title"] = "Inspection Assignment Details"
        context["can_edit_inspections"] = user_can_module_action(
            self.request.user, "inspections", PERMISSION_EDIT
        )
        context["can_update_assignment_status"] = False
        context["inspection_status_stages"] = INSPECTION_STATUS_STAGES
        if self.object.status == "pending" and self.object.inspection_date.date() <= timezone.localdate():
            self.object.status = "in_progress"
            self.object.save(update_fields=["status", "updated_at"])

        self.object.can_change_status = False
        self.object.allowed_statuses = []
        self.object.status_label = {
            "draft": "Draft",
            "pending": "Pending",
            "in_progress": "In Progress",
            "review": "Under Review",
            "completed": "Closed",
            "cancelled": "Cancelled",
        }.get(self.object.status, self.object.status.replace("_", " ").title())
        self.object.status_caption_class = INSPECTION_STATUS_CAPTION_CLASSES.get(
            self.object.status, "is-neutral"
        )
        self.object.status_update_url = reverse_inspection_url(
            self.request, "inspection_status_update", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )

        context["submitted_photos"] = list(
            self.object.gallery_images.select_related("uploaded_by")
            .exclude(file="")
            .order_by("uploaded_at", "id_image")
        )
        context["can_submit_inspection"] = (
            user_can_submit_inspection_work(self.request.user, self.object)
            and self.object.status in INSPECTION_MANUAL_STATUS_VALUES
        )
        context["submission_requirements"] = (
            inspection_assignment_submission_requirements(self.object, self.request.user)
            if context["can_submit_inspection"] else None
        )
        context["can_review_inspection"] = (
            self.object.status == "review"
            and user_can_review_inspection(self.request.user, self.object)
        )
        context["has_field_submission"] = inspection_has_field_submission(self.object)
        context["can_delete_inspection"] = (
            context["can_edit_inspections"]
            and self.object.status in INSPECTION_MANUAL_STATUS_VALUES
            and not context["has_field_submission"]
        )
        context["can_cancel_inspection"] = (
            context["has_field_submission"]
            and self.object.status not in {"completed", "cancelled"}
            and user_can_review_inspection(self.request.user, self.object)
        )
        context["can_close_inspection"] = (
            self.object.status not in {"completed", "cancelled"}
            and user_can_review_inspection(self.request.user, self.object)
        )
        context["is_inspection_locked"] = self.object.status in {"review", "completed", "cancelled"}
        context["can_create_estimate_from_inspection"] = (
            self.object.status == "completed"
            and user_can_module_action(self.request.user, "estimates", PERMISSION_CREATE)
        )
        context["create_estimate_url"] = None
        if context["can_create_estimate_from_inspection"]:
            context["create_estimate_url"] = reverse_estimate_from_inspection_url(
                self.request, self.object, company_slug=company_slug
            )
        context["can_prepare_project_from_inspection"] = (
            not self.object.id_project_id
            and user_can_module_action(self.request.user, "projects", PERMISSION_CREATE)
        )
        context["can_create_project_from_inspection"] = (
            self.object.status == "completed"
            and context["can_prepare_project_from_inspection"]
        )
        context["create_project_url"] = None
        if context["can_create_project_from_inspection"]:
            context["create_project_url"] = reverse_project_from_inspection_url(
                self.request, self.object, company_slug=company_slug
            )
        context["linked_project_url"] = None
        if self.object.id_project_id:
            context["linked_project_url"] = reverse(
                "company_projects:project_detail" if company_slug else "projects:project_detail",
                kwargs={
                    **({"company_slug": company_slug} if company_slug else {}),
                    "id_project": self.object.id_project_id,
                },
            )

        context["inspection_list_url"] = reverse_inspection_url(
            self.request, "inspection_list", company_slug=company_slug
        )
        context["inspection_update_url"] = reverse_inspection_url(
            self.request, "inspection_update", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_delete_url"] = reverse_inspection_url(
            self.request, "inspection_delete", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_submit_review_url"] = reverse_inspection_url(
            self.request, "inspection_submit_review", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_approve_url"] = reverse_inspection_url(
            self.request, "inspection_approve", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_corrections_url"] = reverse_inspection_url(
            self.request, "inspection_request_corrections", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_cancel_url"] = reverse_inspection_url(
            self.request, "inspection_cancel", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["inspection_close_url"] = reverse_inspection_url(
            self.request, "inspection_close", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        self.object.close_url = context["inspection_close_url"]
        self.object.can_close_record = context["can_close_inspection"]
        self.object.can_prepare_project = context["can_prepare_project_from_inspection"]
        self.object.can_open_completion_options = (
            self.object.can_close_record or self.object.can_prepare_project
        )
        self.object.create_project_url = context["create_project_url"] or ""
        context["inspection_contractor_update_url"] = reverse_inspection_url(
            self.request, "inspection_contractor_update", company_slug=company_slug,
            kwargs={"id_assignment": self.object.id_assignment},
        )
        return context


def send_inspection_assignment_email(assignment):
    inspector = assignment.inspector
    client = assignment.client

    if not inspector or not inspector.email:
        return False

    inspector_name = f"{inspector.first_name or ''} {inspector.last_name or ''}".strip()

    if not inspector_name:
        inspector_name = inspector.email

    company = client.id_company if client else inspector.id_company

    send_company_email(
        company=company,
        subject="New Inspection Assignment",
        text_body=(
            f"Hello {inspector_name},\n\n"
            f"You have a new inspection assignment.\n\n"
            f"Client: {client.name if client else 'N/A'}\n"
            f"Phone: {client.phone if client else 'N/A'}\n"
            f"Email: {client.email if client else 'N/A'}\n"
            f"Address: {client.address if client else 'N/A'}\n"
            f"Inspection Date: {assignment.inspection_date or 'N/A'}\n"
            f"Status: {assignment.status or 'N/A'}\n\n"
            f"Please log in to the CRM to review the inspection assignment."
        ),
        to_emails=[inspector.email],
        html_body=None,
    )

    return True
def send_inspection_status_changed_email(assignment, old_status=None, changed_by=None):
    inspector = assignment.inspector
    client = assignment.client

    if not inspector or not inspector.email:
        return False

    inspector_name = f"{inspector.first_name or ''} {inspector.last_name or ''}".strip()

    if not inspector_name:
        inspector_name = inspector.email

    company = client.id_company if client else inspector.id_company

    changed_by_text = "System"

    if changed_by:
        changed_by_text = (
            f"{changed_by.first_name or ''} {changed_by.last_name or ''}".strip()
            or changed_by.email
            or "System"
        )

    send_company_email(
        company=company,
        subject="Inspection Status Updated",
        text_body=(
            f"Hello {inspector_name},\n\n"
            f"The inspection status has been changed successfully.\n\n"
            f"Client: {client.name if client else 'N/A'}\n"
            f"Phone: {client.phone if client else 'N/A'}\n"
            f"Email: {client.email if client else 'N/A'}\n"
            f"Address: {client.address if client else 'N/A'}\n"
            f"Inspection Date: {assignment.inspection_date or 'N/A'}\n"
            f"New Status: {assignment.get_status_display()}\n"
            f"Changed By: {changed_by_text}\n\n"
            f"Please log in to the CRM to review the inspection assignment."
        ),
        to_emails=[inspector.email],
        html_body=None,
    )

    return True

class InspectionAssignmentCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "inspections"
    permission_required = PERMISSION_CREATE
    model = InspectionAssignment
    form_class = InspectionAssignmentForm
    template_name = "inspections/assignment_form.html"
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_inspection_url(
            self.request,
            "inspection_list",
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_valid(self, form):
        form.instance.status = (
            "draft" if self.request.POST.get("save_mode") == "draft" else "pending"
        )
        self.object = form.save()

        if self.object.status == "pending":
            try:
                email_sent = send_inspection_assignment_email(self.object)
                if email_sent:
                    messages.success(
                        self.request,
                        "Inspection created as Pending and the inspector was notified.",
                    )
                else:
                    messages.success(
                        self.request,
                        "Inspection created as Pending. No inspector email was found.",
                    )
            except Exception as error:
                messages.warning(
                    self.request,
                    f"Inspection created as Pending, but email could not be sent: {error}",
                )
        else:
            messages.success(self.request, "Inspection saved as draft.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the inspection assignment form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Assign Inspection"
        context["form_title"] = "Assign Inspection"
        context["submit_label"] = "Save Inspection"
        context["allow_save_draft"] = True
        context["primary_submit_label"] = "Save and set Pending"
        context["cancel_url"] = reverse_inspection_url(
            self.request, "inspection_list", company_slug=self.kwargs.get("company_slug")
        )
        context["client_autofill_data"] = getattr(context["form"], "client_autofill_data", {})

        return context


class InspectionAssignmentUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "inspections"
    permission_required = PERMISSION_EDIT
    model = InspectionAssignment
    template_name = "inspections/assignment_form.html"
    context_object_name = "assignment"
    pk_url_kwarg = "id_assignment"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if user_is_contractor_only(request.user):
            return HttpResponseForbidden(
                "Contractors use the field delivery screen for evidence and notes."
            )
        self.object = self.get_object()
        if self.object.status in {"review", "completed", "cancelled"}:
            messages.error(request, "This inspection is locked. Use the review or cancellation actions.")
            return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=kwargs.get("company_slug"), kwargs={"id_assignment": self.object.id_assignment}))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return inspection_assignment_queryset_for_user(self.request.user)

    def get_form_class(self):
        return InspectionAssignmentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_inspection_url(
            self.request,
            "inspection_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_assignment": self.object.id_assignment},
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

        if previous_status == "draft" and self.object.status == "pending":
            try:
                send_inspection_assignment_email(self.object)
            except Exception as error:
                messages.warning(
                    self.request,
                    f"Inspection updated, but email could not be sent: {error}",
                )

        messages.success(
            self.request,
            "Inspection saved as draft."
            if self.object.status == "draft"
            else "Inspection updated successfully.",
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the inspection form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Edit Inspection"
        context["form_title"] = "Edit Inspection"
        context["submit_label"] = "Update Inspection"
        context["allow_save_draft"] = self.object.status == "draft"
        context["primary_submit_label"] = (
            "Save and set Pending" if self.object.status == "draft" else "Save changes"
        )

        context["cancel_url"] = reverse_inspection_url(
            self.request, "inspection_detail", company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_assignment": self.object.id_assignment},
        )
        context["client_autofill_data"] = getattr(context["form"], "client_autofill_data", {})
        return context



@require_POST
def inspection_assignment_contractor_update_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(
        inspection_assignment_queryset_for_user(request.user),
        id_assignment=id_assignment,
    )
    if not user_can_submit_inspection_work(request.user, assignment):
        return HttpResponseForbidden("You cannot update this inspection delivery.")
    if assignment.status not in INSPECTION_MANUAL_STATUS_VALUES:
        return HttpResponseForbidden("This inspection is locked and cannot be edited.")

    assignment.inspection_notes = (request.POST.get("inspection_notes") or "").strip()
    assignment.recommendations = (request.POST.get("recommendations") or "").strip()
    update_fields = ["inspection_notes", "recommendations", "updated_at"]
    if assignment.status in {"draft", "pending"}:
        assignment.status = "in_progress"
        update_fields.append("status")
    assignment.save(update_fields=update_fields)
    messages.success(request, "Observations and recommendations saved.")
    return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=company_slug, kwargs={"id_assignment": assignment.id_assignment}) + "#field-notes")


@require_POST
def inspection_assignment_submit_review_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(inspection_assignment_queryset_for_user(request.user), id_assignment=id_assignment)
    try:
        submit_inspection_assignment_for_review(
            assignment, request.user,
            notes=request.POST.get("inspection_notes"),
            recommendations=request.POST.get("recommendations"),
            uploads=collect_photo_slots(request),
        )
        messages.success(request, "Inspection evidence was saved as WebP and sent for review.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=company_slug, kwargs={"id_assignment": assignment.id_assignment}))


# Legacy URL callable.
inspection_assignment_submit_audit_view = inspection_assignment_submit_review_view


@require_POST
def inspection_assignment_status_update_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(
        inspection_assignment_queryset_for_user(request.user),
        id_assignment=id_assignment,
    )
    message = (
        "Inspection status is automatic. Use Save Draft, Save Pending, field submission, "
        "review, approval or cancellation actions."
    )
    if inspection_request_wants_json(request):
        return JsonResponse(
            {"ok": False, "status": assignment.status, "message": message}, status=400
        )
    messages.error(request, message)
    return redirect(
        reverse_inspection_url(
            request,
            "inspection_detail",
            company_slug=company_slug,
            kwargs={"id_assignment": assignment.id_assignment},
        )
    )


@require_POST
def inspection_assignment_close_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(
        inspection_assignment_queryset_for_user(request.user),
        id_assignment=id_assignment,
    )
    try:
        close_inspection(assignment, request.user)
        assignment.refresh_from_db()
        messages.success(request, "Inspection closed and frozen successfully.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
        return redirect(
            reverse_inspection_url(
                request,
                "inspection_detail",
                company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
        )

    if request.POST.get("next") == "project":
        if assignment.id_project_id:
            return redirect(
                reverse(
                    "company_projects:project_detail" if company_slug else "projects:project_detail",
                    kwargs={
                        **({"company_slug": company_slug} if company_slug else {}),
                        "id_project": assignment.id_project_id,
                    },
                )
            )
        if user_can_module_action(request.user, "projects", PERMISSION_CREATE):
            return redirect(
                reverse_project_from_inspection_url(
                    request, assignment, company_slug=company_slug
                )
            )
        messages.error(request, "You do not have permission to create projects.")

    return redirect(
        reverse_inspection_url(
            request,
            "inspection_detail",
            company_slug=company_slug,
            kwargs={"id_assignment": assignment.id_assignment},
        )
    )


@require_POST
def inspection_assignment_approve_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(inspection_assignment_queryset_for_user(request.user), id_assignment=id_assignment)
    try:
        approve_inspection_assignment(assignment, request.user)
        messages.success(request, "Inspection approved. Previous states are now locked.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=company_slug, kwargs={"id_assignment": assignment.id_assignment}))


@require_POST
def inspection_assignment_request_corrections_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(inspection_assignment_queryset_for_user(request.user), id_assignment=id_assignment)
    try:
        request_inspection_corrections(assignment, request.user, request.POST.get("correction_reason"))
        messages.success(request, "Corrections requested. The inspection returned to In Progress.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=company_slug, kwargs={"id_assignment": assignment.id_assignment}))


@require_POST
def inspection_assignment_cancel_view(request, id_assignment, company_slug=None):
    assignment = get_object_or_404(inspection_assignment_queryset_for_user(request.user), id_assignment=id_assignment)
    try:
        cancel_inspection(
            assignment,
            request.user,
            request.POST.get("cancel_reason") or request.POST.get("void_reason"),
        )
        messages.success(request, "Inspection cancelled and frozen successfully.")
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    return redirect(reverse_inspection_url(request, "inspection_detail", company_slug=company_slug, kwargs={"id_assignment": assignment.id_assignment}))


def assignment_delete_view(request, id_assignment, company_slug=None):
    if request.method != "POST":
        messages.error(request, "Please confirm deletion from the assignments list.")
        return redirect(
            reverse_inspection_url(
                request,
                "inspection_list",
                company_slug=company_slug,
            )
        )

    permission_response = require_module_action_or_403(
        request.user,
        "inspections",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    queryset = InspectionAssignment.objects.select_related(
        "client",
        "client__id_company",
    )

    if not request.user.is_superuser:
        if not request.user.id_company_id:
            return HttpResponseForbidden("Permission denied.")

        queryset = queryset.filter(
            client__id_company_id=request.user.id_company_id,
        )

    assignment = get_object_or_404(
        queryset,
        id_assignment=id_assignment,
    )

    if inspection_has_field_submission(assignment):
        messages.error(
            request,
            "This inspection already received contractor evidence and cannot be deleted. Cancel it with a reason instead.",
        )
        return redirect(
            reverse_inspection_url(
                request,
                "inspection_detail",
                company_slug=company_slug,
                kwargs={"id_assignment": assignment.id_assignment},
            )
        )
    assignment.delete()

    messages.success(request, "Inspection assignment deleted successfully.")

    return redirect(
        reverse_inspection_url(
            request,
            "inspection_list",
            company_slug=company_slug,
        )
    )

class InspectionViewSet(TenantModelViewSet):
    module_name = "inspections"
    queryset = Inspection.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_inspector",
    ).all()
    serializer_class = InspectionSerializer
    tenant_filter_path = "id_project__id_company"

    def get_queryset(self):
        return inspection_list_for_user(self.request.user)

    def perform_create(self, serializer):
        project = serializer.validated_data.get("id_project")

        if self.request.user.is_superuser:
            serializer.save()
            return

        if not project or project.id_company_id != self.request.user.id_company_id:
            raise PermissionDenied("Project must belong to your company.")

        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()

        if not self.request.user.is_superuser:
            if instance.id_project.id_company_id != self.request.user.id_company_id:
                raise PermissionDenied("You can only update inspections from your company.")

        serializer.save()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        inspection = self.get_object()

        if not user_can_module_action(
            request.user,
            "inspections",
            PERMISSION_APPROVE,
        ):
            raise PermissionDenied("You do not have permission to approve inspections.")

        inspection_approve(inspection)

        return Response(
            {
                "detail": "Inspection marked as completed successfully.",
                "inspection_id": inspection.id_inspection,
            }
        )