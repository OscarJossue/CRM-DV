from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from urllib.parse import urlencode

from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.exceptions import PermissionDenied

from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    user_can_module_action,
    require_module_action_or_403,
)

from .forms import ClientForm
from .models import Client
from .selectors import client_list_for_user
from .serializers import ClientSerializer


def reverse_crm_url(request, app_namespace, company_namespace, view_name, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    slug = company_slug or getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_slug")

    if slug:
        scoped_kwargs = {"company_slug": slug, **kwargs}
        try:
            return reverse(f"{company_namespace}:{view_name}", kwargs=scoped_kwargs)
        except NoReverseMatch:
            pass

    return reverse(f"{app_namespace}:{view_name}", kwargs=kwargs)


def reverse_client_url(request, view_name, company_slug=None, kwargs=None):
    return reverse_crm_url(
        request,
        "clients",
        "company_clients",
        view_name,
        company_slug=company_slug,
        kwargs=kwargs,
    )


def build_client_urls(request, client=None, company_slug=None):
    urls = {
        "list": reverse_client_url(request, "client_list", company_slug=company_slug),
        "create": reverse_client_url(request, "client_create", company_slug=company_slug),
    }

    if client is not None:
        kwargs = {"id_client": client.id_client}
        urls.update(
            {
                "detail": reverse_client_url(request, "client_detail", company_slug=company_slug, kwargs=kwargs),
                "update": reverse_client_url(request, "client_update", company_slug=company_slug, kwargs=kwargs),
                "delete": reverse_client_url(request, "client_delete", company_slug=company_slug, kwargs=kwargs),
            }
        )

    return urls


class ClientListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "clients"
    permission_required = PERMISSION_VIEW
    template_name = "clients/list.html"
    context_object_name = "clients"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = client_list_for_user(self.request.user)
        query = (self.request.GET.get("q") or "").strip()
        legacy_code = (self.request.GET.get("code") or "").strip()
        legacy_name = (self.request.GET.get("name") or "").strip()
        legacy_dni = (self.request.GET.get("dni") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(client_code__icontains=token)
                    | Q(name__icontains=token)
                    | Q(first_name__icontains=token)
                    | Q(middle_name__icontains=token)
                    | Q(last_name__icontains=token)
                    | Q(second_last_name__icontains=token)
                    | Q(dni__icontains=token)
                )

        if legacy_code:
            queryset = queryset.filter(client_code__icontains=legacy_code)
        if legacy_name:
            queryset = queryset.filter(
                Q(name__icontains=legacy_name)
                | Q(first_name__icontains=legacy_name)
                | Q(middle_name__icontains=legacy_name)
                | Q(last_name__icontains=legacy_name)
                | Q(second_last_name__icontains=legacy_name)
            )
        if legacy_dni:
            queryset = queryset.filter(dni__icontains=legacy_dni)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Clients"
        context["can_view_clients"] = user_can_module_action(
            self.request.user,
            "clients",
            PERMISSION_VIEW,
        )
        context["can_create_clients"] = user_can_module_action(
            self.request.user,
            "clients",
            PERMISSION_CREATE,
        )
        context["can_edit_clients"] = user_can_module_action(
            self.request.user,
            "clients",
            PERMISSION_EDIT,
        )

        company_slug = self.kwargs.get("company_slug")
        context["client_urls"] = build_client_urls(
            self.request,
            company_slug=company_slug,
        )
        for client in context.get("clients", []):
            client.ui_urls = build_client_urls(
                self.request,
                client,
                company_slug=company_slug,
            )

        context["client_filters"] = {"q": self.request.GET.get("q", "")}
        filter_params = self.request.GET.copy()
        filter_params.pop("page", None)
        context["client_filter_query"] = urlencode(filter_params, doseq=True)
        return context


class ClientDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "clients"
    permission_required = PERMISSION_VIEW
    model = Client
    template_name = "clients/detail.html"
    context_object_name = "client"
    pk_url_kwarg = "id_client"
    login_url = "/login/"

    def get_queryset(self):
        return client_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Client Details"
        context["can_edit_clients"] = user_can_module_action(
            self.request.user,
            "clients",
            PERMISSION_EDIT,
        )

        company_slug = self.kwargs.get("company_slug")
        context["client_urls"] = build_client_urls(
            self.request,
            self.object,
            company_slug=company_slug,
        )

        try:
            projects = list(self.object.projects.all().order_by("-created_at")[:8])
            for project in projects:
                project.ui_detail_url = reverse_crm_url(
                    self.request,
                    "projects",
                    "company_projects",
                    "project_detail",
                    company_slug=company_slug,
                    kwargs={"id_project": project.id_project},
                )
            context["client_projects"] = projects
        except Exception:
            context["client_projects"] = []

        try:
            invoices = list(self.object.invoices.all().order_by("-issue_date", "-id_invoice")[:8])
            for invoice in invoices:
                invoice.ui_detail_url = reverse_crm_url(
                    self.request,
                    "invoices",
                    "company_invoices",
                    "invoice_detail",
                    company_slug=company_slug,
                    kwargs={"id_invoice": invoice.id_invoice},
                )
            context["client_invoices"] = invoices
        except Exception:
            context["client_invoices"] = []

        try:
            payments = list(self.object.payments.all().order_by("-payment_date", "-id_payment")[:8])
            for payment in payments:
                payment.ui_detail_url = reverse_crm_url(
                    self.request,
                    "payments",
                    "company_payments",
                    "payment_detail",
                    company_slug=company_slug,
                    kwargs={"id_payment": payment.id_payment},
                )
            context["client_payments"] = payments
        except Exception:
            context["client_payments"] = []

        return context


class ClientCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "clients"
    permission_required = PERMISSION_CREATE
    model = Client
    form_class = ClientForm
    template_name = "clients/form.html"
    login_url = "/login/"

    def get_success_url(self):
        return reverse_client_url(
            self.request,
            "client_list",
            company_slug=self.kwargs.get("company_slug"),
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Client created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the client form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Create Client"
        context["form_title"] = "Create Client"
        context["submit_label"] = "Save Client"
        context["client_urls"] = build_client_urls(
            self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

        return context


class ClientUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "clients"
    permission_required = PERMISSION_EDIT
    model = Client
    form_class = ClientForm
    template_name = "clients/form.html"
    context_object_name = "client"
    pk_url_kwarg = "id_client"
    login_url = "/login/"

    def get_queryset(self):
        return client_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_client_url(
            self.request,
            "client_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_client": self.object.id_client},
        )

    def form_valid(self, form):
        messages.success(self.request, "Client updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the client form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Edit Client"
        context["form_title"] = "Edit Client"
        context["submit_label"] = "Update Client"
        context["client_urls"] = build_client_urls(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )

        return context


@login_required(login_url="/login/")
def client_delete_view(request, id_client, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "clients",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    client = get_object_or_404(
        client_list_for_user(request.user),
        id_client=id_client,
    )

    if not request.user.is_superuser:
        if not request.user.id_company_id:
            return HttpResponseForbidden("Permission denied.")

        if client.id_company_id != request.user.id_company_id:
            return HttpResponseForbidden("Permission denied.")

    if request.method != "POST":
        messages.error(request, "Please use the confirmation modal to delete a client.")

        return redirect(
            reverse_client_url(
                request,
                "client_list",
                company_slug=company_slug,
            )
        )

    try:
        client.delete()
    except ProtectedError:
        messages.error(
            request,
            "This client cannot be deleted because it has related projects, invoices, payments, credits, or contracts.",
        )
        return redirect(
            reverse_client_url(
                request,
                "client_detail",
                company_slug=company_slug,
                kwargs={"id_client": client.id_client},
            )
        )

    messages.success(request, "Client deleted successfully.")

    return redirect(
        reverse_client_url(
            request,
            "client_list",
            company_slug=company_slug,
        )
    )

class ClientViewSet(TenantModelViewSet):
    module_name = "clients"
    queryset = Client.objects.select_related("id_company").all()
    serializer_class = ClientSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return client_list_for_user(self.request.user)

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
            raise PermissionDenied("You can only update clients from your company.")

        serializer.save(id_company=self.request.user.id_company)