from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models.choices import TENANT_MODULE_CHOICES
from apps.companies.models import Company

from .forms import CompanyModuleForm
from .models import CompanyModule
from .permissions import (
    user_can_access_company_module,
    user_can_manage_company_modules,
)
from .selectors import company_module_list_for_user
from .serializers import CompanyModuleSerializer
from .services import bulk_update_company_modules, sync_company_modules


class CompanyModuleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "company_modules/list.html"
    context_object_name = "company_modules"
    paginate_by = 30
    login_url = "/login/"

    def test_func(self):
        return user_can_manage_company_modules(self.request.user)

    def get_queryset(self):
        return company_module_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Company Modules"
        return context


class CompanyModuleDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = CompanyModule
    template_name = "company_modules/detail.html"
    context_object_name = "company_module"
    pk_url_kwarg = "id_company_module"
    login_url = "/login/"

    def test_func(self):
        company_module = self.get_object()

        return user_can_manage_company_modules(
            self.request.user
        ) and user_can_access_company_module(
            self.request.user,
            company_module,
        )

    def get_queryset(self):
        return company_module_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Company Module Details"
        return context


class CompanyModuleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CompanyModule
    form_class = CompanyModuleForm
    template_name = "company_modules/form.html"
    success_url = reverse_lazy("company_modules:company_module_list")
    login_url = "/login/"

    def test_func(self):
        return user_can_manage_company_modules(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Company module created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the company module form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Company Module"
        context["form_title"] = "Create Company Module"
        context["submit_label"] = "Save Module"
        return context


class CompanyModuleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CompanyModule
    form_class = CompanyModuleForm
    template_name = "company_modules/form.html"
    context_object_name = "company_module"
    pk_url_kwarg = "id_company_module"
    login_url = "/login/"

    def test_func(self):
        company_module = self.get_object()

        return user_can_manage_company_modules(
            self.request.user
        ) and user_can_access_company_module(
            self.request.user,
            company_module,
        )

    def get_queryset(self):
        return company_module_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy(
            "company_modules:company_module_detail",
            kwargs={"id_company_module": self.object.id_company_module},
        )

    def form_valid(self, form):
        messages.success(self.request, "Company module updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the company module form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Company Module"
        context["form_title"] = "Edit Company Module"
        context["submit_label"] = "Update Module"
        return context


class CompanyModuleManageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "company_modules/manage.html"
    login_url = "/login/"

    def test_func(self):
        return user_can_manage_company_modules(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(
            Company,
            id_company=self.kwargs.get("id_company"),
        )

        sync_company_modules(self.company, default_enabled=True)

        return super().dispatch(request, *args, **kwargs)

    def get_module_rows(self):
        module_map = {
            company_module.module: company_module
            for company_module in CompanyModule.objects.filter(id_company=self.company)
        }

        rows = []

        for module_value, module_label in TENANT_MODULE_CHOICES:
            company_module = module_map.get(module_value)

            rows.append(
                {
                    "module": module_value,
                    "module_label": module_label,
                    "is_enabled": company_module.is_enabled if company_module else False,
                }
            )

        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Manage Company Modules"
        context["company"] = self.company
        context["module_rows"] = self.get_module_rows()

        return context

    def post(self, request, *args, **kwargs):
        enabled_modules = request.POST.getlist("enabled_modules")

        bulk_update_company_modules(
            self.company,
            enabled_modules,
        )

        messages.success(request, "Company modules updated successfully.")

        return redirect(
            "company_modules:company_module_manage",
            id_company=self.company.id_company,
        )


@require_POST
def company_module_sync_view(request, id_company):
    if not user_can_manage_company_modules(request.user):
        return HttpResponseForbidden("Permission denied.")

    company = get_object_or_404(Company, id_company=id_company)

    sync_company_modules(company, default_enabled=True)

    messages.success(request, "Company modules synced successfully.")

    return redirect(
        "company_modules:company_module_manage",
        id_company=company.id_company,
    )


class CompanyModuleViewSet(viewsets.ModelViewSet):
    queryset = CompanyModule.objects.select_related("id_company").all()
    serializer_class = CompanyModuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.queryset

        return self.queryset.filter(id_company=self.request.user.id_company_id)

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can create company modules.")

        serializer.save()

    def perform_update(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can update company modules.")

        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers can delete company modules.")

        instance.delete()
