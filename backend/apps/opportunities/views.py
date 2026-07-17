from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
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

from .forms import LeadForm
from .models import Lead
from .models.choices import (
    LEAD_SOURCE_CHOICES,
    OPPORTUNITY_STATUS_CHOICES,
    OPPORTUNITY_STATUS_CANCELLED,
    OPPORTUNITY_STATUS_CONVERTED,
    OPPORTUNITY_STATUS_NEW,
    OPPORTUNITY_STATUS_QUALIFIED,
    OPPORTUNITY_STATUS_WON,
)
from .permissions import user_can_access_lead
from .selectors import lead_list_for_user
from .serializers import LeadSerializer
from .services import convert_lead_to_project


def reverse_crm_url(
    request,
    app_namespace,
    company_namespace,
    view_name,
    company_slug=None,
    kwargs=None,
):
    kwargs = dict(kwargs or {})
    slug = company_slug or getattr(
        getattr(request, "resolver_match", None),
        "kwargs",
        {},
    ).get("company_slug")

    if slug:
        scoped_kwargs = {"company_slug": slug, **kwargs}
        try:
            return reverse(f"{company_namespace}:{view_name}", kwargs=scoped_kwargs)
        except NoReverseMatch:
            pass

    return reverse(f"{app_namespace}:{view_name}", kwargs=kwargs)


def reverse_opportunity_url(request, view_name, company_slug=None, kwargs=None):
    return reverse_crm_url(
        request,
        "opportunities",
        "company_opportunities",
        view_name,
        company_slug=company_slug,
        kwargs=kwargs,
    )


def build_opportunity_urls(request, lead=None, company_slug=None):
    urls = {
        "list": reverse_opportunity_url(
            request,
            "opportunity_list",
            company_slug=company_slug,
        ),
        "create": reverse_opportunity_url(
            request,
            "opportunity_create",
            company_slug=company_slug,
        ),
    }

    if lead is None:
        return urls

    lead_kwargs = {"id_lead": lead.id_lead}
    urls.update(
        {
            "detail": reverse_opportunity_url(
                request,
                "opportunity_detail",
                company_slug=company_slug,
                kwargs=lead_kwargs,
            ),
            "update": reverse_opportunity_url(
                request,
                "opportunity_update",
                company_slug=company_slug,
                kwargs=lead_kwargs,
            ),
            "delete": reverse_opportunity_url(
                request,
                "opportunity_delete",
                company_slug=company_slug,
                kwargs=lead_kwargs,
            ),
            "status_update": reverse_opportunity_url(
                request,
                "opportunity_status_update",
                company_slug=company_slug,
                kwargs=lead_kwargs,
            ),
            "convert": reverse_opportunity_url(
                request,
                "opportunity_convert",
                company_slug=company_slug,
                kwargs=lead_kwargs,
            ),
            "client_detail": None,
            "project_detail": None,
        }
    )

    project_create = reverse_crm_url(
        request,
        "projects",
        "company_projects",
        "project_create",
        company_slug=company_slug,
    )
    urls["project_create"] = f"{project_create}?{urlencode({'opportunity_id': lead.id_lead})}"

    if lead.id_client_id:
        urls["client_detail"] = reverse_crm_url(
            request,
            "clients",
            "company_clients",
            "client_detail",
            company_slug=company_slug,
            kwargs={"id_client": lead.id_client_id},
        )

    if lead.id_converted_project_id:
        urls["project_detail"] = reverse_crm_url(
            request,
            "projects",
            "company_projects",
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": lead.id_converted_project_id},
        )

    return urls


OPPORTUNITY_STATUS_UI = {
    OPPORTUNITY_STATUS_NEW: {"stage": "new", "caption_class": "is-blue"},
    OPPORTUNITY_STATUS_QUALIFIED: {"stage": "qualified", "caption_class": "is-violet"},
    OPPORTUNITY_STATUS_WON: {"stage": "won", "caption_class": "is-success"},
    OPPORTUNITY_STATUS_CONVERTED: {"stage": "converted", "caption_class": "is-success"},
    OPPORTUNITY_STATUS_CANCELLED: {"stage": "cancelled", "caption_class": "is-void"},
}


def apply_opportunity_ui_state(opportunity):
    ui = OPPORTUNITY_STATUS_UI.get(
        getattr(opportunity, "status", None),
        OPPORTUNITY_STATUS_UI[OPPORTUNITY_STATUS_NEW],
    )
    opportunity.status_stage_key = ui["stage"]
    opportunity.status_caption_class = ui["caption_class"]
    return opportunity


class LeadListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "opportunities"
    permission_required = PERMISSION_VIEW
    template_name = "opportunities/list.html"
    context_object_name = "leads"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        base_queryset = lead_list_for_user(self.request.user).select_related(
            "id_company",
            "id_client",
            "id_assigned_user",
            "id_converted_project",
        )
        self.opportunity_base_queryset = base_queryset
        queryset = base_queryset

        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        # Backwards-compatible support for old bookmarked filters.
        legacy_code = (self.request.GET.get("code") or "").strip()
        legacy_name = (self.request.GET.get("name") or "").strip()
        legacy_dni = (self.request.GET.get("dni") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(opportunity_code__icontains=token)
                    | Q(id_client__client_code__icontains=token)
                    | Q(id_client__name__icontains=token)
                    | Q(id_client__first_name__icontains=token)
                    | Q(id_client__middle_name__icontains=token)
                    | Q(id_client__last_name__icontains=token)
                    | Q(id_client__second_last_name__icontains=token)
                    | Q(id_client__dni__icontains=token)
                )

        if legacy_code:
            queryset = queryset.filter(
                Q(opportunity_code__icontains=legacy_code)
                | Q(id_client__client_code__icontains=legacy_code)
            )

        if legacy_name:
            queryset = queryset.filter(
                Q(id_client__name__icontains=legacy_name)
                | Q(id_client__first_name__icontains=legacy_name)
                | Q(id_client__middle_name__icontains=legacy_name)
                | Q(id_client__last_name__icontains=legacy_name)
                | Q(id_client__second_last_name__icontains=legacy_name)
            )

        if legacy_dni:
            queryset = queryset.filter(id_client__dni__icontains=legacy_dni)

        valid_statuses = {value for value, _label in OPPORTUNITY_STATUS_CHOICES}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Opportunities"
        context["can_view_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_VIEW,
        )
        context["can_create_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_CREATE,
        )
        context["can_edit_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_EDIT,
        )
        context["can_approve_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_APPROVE,
        )

        company_slug = self.kwargs.get("company_slug")
        for opportunity in context.get("leads", []):
            opportunity.ui_urls = build_opportunity_urls(
                self.request,
                opportunity,
                company_slug=company_slug,
            )
            apply_opportunity_ui_state(opportunity)

        current_query = self.request.GET.get("q", "")
        current_status = self.request.GET.get("status", "")
        context["filters"] = {"q": current_query, "status": current_status}
        context["current_opportunity_status"] = current_status
        context["opportunity_urls"] = build_opportunity_urls(
            self.request,
            company_slug=company_slug,
        )

        base_queryset = getattr(
            self,
            "opportunity_base_queryset",
            lead_list_for_user(self.request.user),
        )
        status_counts = {
            row["status"]: row["total"]
            for row in base_queryset.values("status").annotate(total=Count("id_lead"))
        }
        totals = base_queryset.aggregate(
            total_count=Count("id_lead"),
            total_value=Sum("approximate_value"),
        )
        context["opportunity_total_count"] = totals["total_count"] or 0
        context["opportunity_total_value"] = totals["total_value"] or 0
        context["opportunity_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {"value": OPPORTUNITY_STATUS_NEW, "label": "New", "caption": "New commercial opportunities", "icon": "bi-plus-lg", "color": "#0868e8"},
                {"value": OPPORTUNITY_STATUS_QUALIFIED, "label": "Qualified", "caption": "Validated and ready to advance", "icon": "bi-stars", "color": "#7c3aed"},
                {"value": OPPORTUNITY_STATUS_WON, "label": "Won", "caption": "Commercially accepted", "icon": "bi-trophy", "color": "#0e9f6e"},
                {"value": OPPORTUNITY_STATUS_CONVERTED, "label": "Converted", "caption": "Converted into projects", "icon": "bi-briefcase", "color": "#0f8f83"},
                {"value": OPPORTUNITY_STATUS_CANCELLED, "label": "Cancelled", "caption": "Closed without conversion", "icon": "bi-x-lg", "color": "#6b7280"},
            ],
            status_counts,
            active_value=current_status,
        )

        filter_params = self.request.GET.copy()
        filter_params.pop("page", None)
        context["opportunity_filter_query"] = urlencode(filter_params, doseq=True)
        return context


class LeadDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "opportunities"
    permission_required = PERMISSION_VIEW
    model = Lead
    template_name = "opportunities/detail.html"
    context_object_name = "lead"
    pk_url_kwarg = "id_lead"
    login_url = "/login/"

    def get_queryset(self):
        return lead_list_for_user(self.request.user).select_related(
            "id_client",
            "id_assigned_user",
            "id_converted_project",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_opportunity_ui_state(self.object)
        context["page_title"] = "Opportunity Details"
        context["can_edit_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_EDIT,
        )
        context["can_approve_opportunities"] = user_can_module_action(
            self.request.user,
            "opportunities",
            PERMISSION_APPROVE,
        )
        context["opportunity_urls"] = build_opportunity_urls(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )
        return context


class LeadCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "opportunities"
    permission_required = PERMISSION_CREATE
    model = Lead
    form_class = LeadForm
    template_name = "opportunities/form.html"
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_opportunity_url(
            self.request,
            "opportunity_list",
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Opportunity saved successfully.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the opportunity form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Opportunity"
        context["form_title"] = "Create Opportunity"
        context["submit_label"] = "Save Opportunity"
        context["opportunity_urls"] = build_opportunity_urls(
            self.request,
            company_slug=self.kwargs.get("company_slug"),
        )
        return context


class LeadUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "opportunities"
    permission_required = PERMISSION_EDIT
    model = Lead
    form_class = LeadForm
    template_name = "opportunities/form.html"
    context_object_name = "lead"
    pk_url_kwarg = "id_lead"
    login_url = "/login/"

    def get_queryset(self):
        return lead_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_opportunity_url(
            self.request,
            "opportunity_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_lead": self.object.id_lead},
        )

    def form_valid(self, form):
        messages.success(self.request, "Opportunity updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the opportunity form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Opportunity"
        context["form_title"] = "Edit Opportunity"
        context["submit_label"] = "Update Opportunity"
        context["opportunity_urls"] = build_opportunity_urls(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )
        return context


@login_required(login_url="/login/")
@require_POST
def lead_status_update_view(request, id_lead, company_slug=None):
    """Update an opportunity status from the list workflow control."""
    if not user_can_module_action(
        request.user,
        "opportunities",
        PERMISSION_EDIT,
    ):
        return JsonResponse(
            {"ok": False, "message": "You do not have permission to edit opportunities."},
            status=403,
        )

    lead = get_object_or_404(
        lead_list_for_user(request.user),
        id_lead=id_lead,
    )
    if not user_can_access_lead(request.user, lead):
        return JsonResponse(
            {"ok": False, "message": "Permission denied."},
            status=403,
        )

    requested_status = (request.POST.get("status") or "").strip().lower()
    editable_statuses = {
        OPPORTUNITY_STATUS_NEW,
        OPPORTUNITY_STATUS_QUALIFIED,
        OPPORTUNITY_STATUS_WON,
        OPPORTUNITY_STATUS_CANCELLED,
    }

    if lead.id_converted_project_id:
        return JsonResponse(
            {
                "ok": False,
                "message": "A converted opportunity is linked to a project and its status cannot be changed manually.",
            },
            status=409,
        )

    if requested_status == OPPORTUNITY_STATUS_CONVERTED:
        return JsonResponse(
            {
                "ok": False,
                "message": "Converted is assigned automatically when the opportunity is converted to a project.",
            },
            status=400,
        )

    if requested_status not in editable_statuses:
        return JsonResponse(
            {"ok": False, "message": "Select a valid opportunity status."},
            status=400,
        )

    if lead.status != requested_status:
        lead.status = requested_status
        lead.save(update_fields=["status", "updated_at"])

    status_labels = dict(OPPORTUNITY_STATUS_CHOICES)
    return JsonResponse(
        {
            "ok": True,
            "status": lead.status,
            "label": status_labels.get(lead.status, lead.status.title()),
        }
    )


@login_required(login_url="/login/")
@require_POST
def lead_convert_view(request, id_lead, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "opportunities",
        PERMISSION_APPROVE,
    )
    if permission_response:
        return permission_response

    lead = get_object_or_404(
        lead_list_for_user(request.user),
        id_lead=id_lead,
    )
    if not user_can_access_lead(request.user, lead):
        return HttpResponseForbidden("Permission denied.")

    try:
        project = convert_lead_to_project(lead=lead, user=request.user)
        messages.success(request, "Opportunity converted to project successfully.")
        return redirect(
            reverse_crm_url(
                request,
                "projects",
                "company_projects",
                "project_detail",
                company_slug=company_slug,
                kwargs={"id_project": project.id_project},
            )
        )
    except Exception as error:
        messages.error(request, f"Opportunity could not be converted: {error}")
        return redirect(
            reverse_opportunity_url(
                request,
                "opportunity_detail",
                company_slug=company_slug,
                kwargs={"id_lead": lead.id_lead},
            )
        )


@login_required(login_url="/login/")
@require_POST
def lead_delete_view(request, id_lead, company_slug=None):
    list_url = reverse_opportunity_url(
        request,
        "opportunity_list",
        company_slug=company_slug,
    )

    permission_response = require_module_action_or_403(
        request.user,
        "opportunities",
        PERMISSION_EDIT,
    )
    if permission_response:
        return permission_response

    lead = get_object_or_404(
        lead_list_for_user(request.user),
        id_lead=id_lead,
    )
    if not user_can_access_lead(request.user, lead):
        return HttpResponseForbidden("Permission denied.")

    if lead.id_converted_project_id:
        messages.error(
            request,
            "This opportunity cannot be deleted because it was already converted to a project.",
        )
        return redirect(
            reverse_opportunity_url(
                request,
                "opportunity_detail",
                company_slug=company_slug,
                kwargs={"id_lead": lead.id_lead},
            )
        )

    lead.delete()
    messages.success(request, "Opportunity deleted successfully.")
    return redirect(list_url)


class LeadViewSet(TenantModelViewSet):
    module_name = "opportunities"
    queryset = Lead.objects.select_related(
        "id_company",
        "id_client",
        "id_assigned_user",
        "id_converted_project",
    ).all()
    serializer_class = LeadSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return lead_list_for_user(self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        serializer.save(
            id_company=self.request.user.id_company,
            id_assigned_user=self.request.user,
        )

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        if instance.id_company_id != self.request.user.id_company_id:
            raise PermissionDenied("You can only update opportunities from your company.")

        serializer.save(id_company=self.request.user.id_company)

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        if not user_can_module_action(
            request.user,
            "opportunities",
            PERMISSION_APPROVE,
        ):
            raise PermissionDenied("You do not have permission to convert opportunities.")

        lead = self.get_object()
        project = convert_lead_to_project(lead=lead, user=request.user)
        return Response(
            {
                "detail": "Opportunity converted successfully.",
                "project_id": project.id_project,
            }
        )
