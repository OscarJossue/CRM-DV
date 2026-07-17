from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from rest_framework.exceptions import MethodNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.accounts.views import (
    get_active_company_slug,
    redirect_to_company_user_detail,
    redirect_to_company_user_list,
    user_account_activate_view,
    user_account_deactivate_view,
)
from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    user_can_module_action,
)

from .models import Employee
from .selectors import employee_list_for_user
from .serializers import EmployeeSerializer


def _guard(request, permission):
    if user_can_module_action(request.user, "users", permission):
        return None
    return HttpResponseForbidden("Permission denied.")


def _unified_create_redirect(request, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)
    if active_slug:
        return redirect(f"/{active_slug}/users/create/")
    return redirect("accounts:user_account_create")


def _unified_edit_redirect(request, employee, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)
    if active_slug:
        return redirect(f"/{active_slug}/users/{employee.id_user_id}/edit/")
    return redirect("accounts:user_account_update", id_user=employee.id_user_id)


class EmployeeListView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        denied = _guard(request, PERMISSION_VIEW)
        return denied or redirect_to_company_user_list(request, kwargs.get("company_slug"))


class EmployeeCreateView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        denied = _guard(request, PERMISSION_CREATE)
        return denied or _unified_create_redirect(request, kwargs.get("company_slug"))

    post = get


class EmployeeDetailView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, id_employee, *args, **kwargs):
        denied = _guard(request, PERMISSION_VIEW)
        if denied:
            return denied
        employee = get_object_or_404(employee_list_for_user(request.user), id_employee=id_employee)
        return redirect_to_company_user_detail(request, employee.id_user, kwargs.get("company_slug"))


class EmployeeUpdateView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, id_employee, *args, **kwargs):
        denied = _guard(request, PERMISSION_EDIT)
        if denied:
            return denied
        employee = get_object_or_404(employee_list_for_user(request.user), id_employee=id_employee)
        return _unified_edit_redirect(request, employee, kwargs.get("company_slug"))

    post = get


def employee_activate_view(request, id_employee, company_slug=None):
    employee = get_object_or_404(employee_list_for_user(request.user), id_employee=id_employee)
    return user_account_activate_view(request, employee.id_user_id, company_slug=company_slug)


def employee_deactivate_view(request, id_employee, company_slug=None):
    employee = get_object_or_404(employee_list_for_user(request.user), id_employee=id_employee)
    return user_account_deactivate_view(request, employee.id_user_id, company_slug=company_slug)


class EmployeeViewSet(TenantModelViewSet):
    module_name = "users"
    queryset = Employee.objects.select_related("id_user", "id_company", "id_user__id_role").all()
    serializer_class = EmployeeSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail="Employee profiles are managed through the unified user account.",
        )
