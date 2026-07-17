from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

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
from .permissions import user_can_access_lead
from .selectors import lead_list_for_user
from .serializers import LeadSerializer
from .services import convert_lead_to_client


class LeadListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "leads"
    permission_required = PERMISSION_VIEW
    template_name = "leads/list.html"
    context_object_name = "leads"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        return lead_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Leads"
        context["can_view_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_VIEW,
        )
        context["can_create_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_CREATE,
        )
        context["can_edit_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_EDIT,
        )
        context["can_approve_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_APPROVE,
        )
        return context


class LeadDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "leads"
    permission_required = PERMISSION_VIEW
    model = Lead
    template_name = "leads/detail.html"
    context_object_name = "lead"
    pk_url_kwarg = "id_lead"
    login_url = "/login/"

    def get_queryset(self):
        return lead_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Lead Details"
        context["can_edit_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_EDIT,
        )
        context["can_approve_leads"] = user_can_module_action(
            self.request.user,
            "leads",
            PERMISSION_APPROVE,
        )
        return context


class LeadCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "leads"
    permission_required = PERMISSION_CREATE
    model = Lead
    form_class = LeadForm
    template_name = "leads/form.html"
    success_url = reverse_lazy("leads:lead_list")
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Lead created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the lead form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Lead"
        context["form_title"] = "Create Lead"
        context["submit_label"] = "Save Lead"
        return context


class LeadUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "leads"
    permission_required = PERMISSION_EDIT
    model = Lead
    form_class = LeadForm
    template_name = "leads/form.html"
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
        return reverse_lazy(
            "leads:lead_detail",
            kwargs={"id_lead": self.object.id_lead},
        )

    def form_valid(self, form):
        messages.success(self.request, "Lead updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the lead form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Lead"
        context["form_title"] = "Edit Lead"
        context["submit_label"] = "Update Lead"
        return context


@require_POST
def lead_convert_view(request, id_lead, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "leads",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    lead = get_object_or_404(Lead, id_lead=id_lead)

    if not user_can_access_lead(request.user, lead):
        return HttpResponseForbidden("Permission denied.")

    client = convert_lead_to_client(lead)
    messages.success(request, "Lead converted to client successfully.")

    return redirect("clients:client_detail", id_client=client.id_client)


class LeadViewSet(TenantModelViewSet):
    module_name = "leads"
    queryset = Lead.objects.select_related(
        "id_company",
        "id_assigned_user",
        "id_converted_client",
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

        serializer.save(id_company=self.request.user.id_company)

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()

        if instance.id_company_id != self.request.user.id_company_id:
            raise PermissionDenied("You can only update leads from your company.")

        serializer.save(id_company=self.request.user.id_company)

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        if not user_can_module_action(request.user, "leads", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to convert leads.")

        lead = self.get_object()
        client = convert_lead_to_client(lead)

        return Response(
            {
                "detail": "Lead converted to client successfully.",
                "client_id": client.id_client,
            }
        )
