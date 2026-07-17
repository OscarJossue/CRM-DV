from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseForbidden
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import translation
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import TenantModelViewSet
from apps.core.permissions import HasModulePermission
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)

from .forms import (
    CRMLoginForm,
    RoleForm,
    UserAccountCreateForm,
    UserAccountUpdateForm,
    company_active_user_limit_reached,
    get_company_active_user_count,
    get_company_user_limit,
    get_company_user_limit_message,
)
from .models import Role, RolePermission, UserAccount
from .models.choices import MODULE_CHOICES, STATUS_ACTIVE
from .selectors import (
    role_get_for_user,
    role_list_for_user,
    role_permission_list_for_user,
    user_account_list_for_user,
)
from .serializers import RolePermissionSerializer, RoleSerializer, UserAccountSerializer
from .services import (
    sync_role_permissions_from_post,
    user_account_activate,
    user_account_deactivate,
)
from apps.core.redirects import get_user_dashboard_url


EXCLUDED_ROLE_MODULES_FOR_COMPANY_USERS = {
    "dashboard",
    "companies",
    "company_modules",
    "employees",
    "platform_dashboard",
    "platform_companies",
    "platform_plans",
    "platform_subscriptions",
    "platform_documents",
    "platform_payments",
    "platform_calendar",
    "platform_email",
    "platform_notifications",
    "platform_audit",
    "platform_metrics",
    "platform_system_monitor",
}


def get_active_company_slug(request, company_slug=None):
    if company_slug:
        return company_slug

    current_company = getattr(request, "current_company", None)

    if current_company and getattr(current_company, "slug", None):
        return current_company.slug

    user_company = getattr(request.user, "id_company", None)

    if user_company and getattr(user_company, "slug", None):
        return user_company.slug

    return None


def redirect_to_company_user_list(request, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/users/")

    return redirect("accounts:user_account_list")


def redirect_to_company_user_detail(request, user_account, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/users/{user_account.id_user}/")

    return redirect("accounts:user_account_detail", id_user=user_account.id_user)



def redirect_to_company_role_list(request, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/roles/")

    return redirect("accounts:role_list")


def redirect_to_company_role_detail(request, role, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/roles/{role.id_role}/")

    return redirect("accounts:role_detail", id_role=role.id_role)


def unique_module_choices():
    seen = set()
    clean_choices = []

    for module_value, module_label in MODULE_CHOICES:
        if module_value in seen:
            continue

        if module_value == "employees":
            continue

        seen.add(module_value)
        clean_choices.append((module_value, module_label))

    return clean_choices


def company_module_is_enabled(company, module_value):
    if not company:
        return False

    try:
        from apps.company_modules.selectors import company_has_module_enabled

        try:
            return company_has_module_enabled(company, module_value)
        except TypeError:
            return company_has_module_enabled(company.id_company, module_value)
    except Exception:
        return True


def get_company_for_role_form(user, role=None):
    if role and role.pk:
        return role.id_company

    if user and user.is_authenticated:
        return user.id_company

    return None


def get_role_module_choices_for_user(user, role=None):
    if not user or not user.is_authenticated:
        return []

    company = get_company_for_role_form(user, role)

    if not company:
        return []

    filtered_choices = []

    for module_value, module_label in unique_module_choices():
        if module_value in EXCLUDED_ROLE_MODULES_FOR_COMPANY_USERS:
            continue

        if not company_module_is_enabled(company, module_value):
            continue

        filtered_choices.append((module_value, module_label))

    return filtered_choices


def get_permission_rows_for_role(user, role=None):
    permission_map = {}

    if role and role.pk:
        permission_map = {
            permission.module: permission
            for permission in role.permissions.all()
        }

    rows = []

    for module_value, module_label in get_role_module_choices_for_user(
        user,
        role=role,
    ):
        permission = permission_map.get(module_value)

        can_view = permission.can_view if permission else False
        can_manage = False
        can_approve = False

        if permission:
            can_manage = bool(
                permission.can_create
                or permission.can_edit
                or permission.can_delete
            )
            can_approve = permission.can_approve

        rows.append(
            {
                "module": module_value,
                "module_label": module_label,
                "can_view": can_view,
                "can_manage": can_manage,
                "can_approve": can_approve,
            }
        )

    return rows


class CRMLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = CRMLoginForm
    redirect_authenticated_user = True
    supported_login_languages = {"en", "es"}

    def dispatch(self, request, *args, **kwargs):
        # Respect an explicit language selector first, then the persisted
        # language cookie. Never reset an anonymous visitor to English on the
        # next request after they selected Spanish.
        if request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        requested_language = (
            request.GET.get("language") or ""
        ).strip().lower().split("-")[0]
        cookie_language = (
            request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, "") or ""
        ).strip().lower().split("-")[0]
        active_language = (
            translation.get_language() or ""
        ).strip().lower().split("-")[0]

        if requested_language in self.supported_login_languages:
            login_language = requested_language
        elif cookie_language in self.supported_login_languages:
            login_language = cookie_language
        elif active_language in self.supported_login_languages:
            login_language = active_language
        else:
            login_language = "en"

        translation.activate(login_language)
        request.LANGUAGE_CODE = login_language
        request.crm_language = login_language

        response = super().dispatch(request, *args, **kwargs)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            login_language,
            max_age=60 * 60 * 24 * 365,
            path="/",
            secure=request.is_secure(),
            httponly=False,
            samesite="Lax",
        )
        response["Content-Language"] = login_language
        return response

    def get_success_url(self):
        return get_user_dashboard_url(self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)

        if self.request.POST.get("remember_me"):
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            self.request.session.set_expiry(0)

        user = self.request.user
        cookie_language = (
            self.request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, "") or ""
        ).lower().split("-")[0]
        stored_language = (
            getattr(user, "preferred_language", "en") or "en"
        ).lower().split("-")[0]
        requested_language = (
            self.request.GET.get("language") or ""
        ).lower().split("-")[0]
        selected_language = (
            requested_language
            if requested_language in {"en", "es"}
            else cookie_language
            if cookie_language in {"en", "es"}
            else stored_language
        )
        if selected_language not in {"en", "es"}:
            selected_language = "en"

        if user.is_superuser or user.is_staff:
            if getattr(user, "preferred_language", "en") != selected_language:
                user.preferred_language = selected_language
                user.save(update_fields=["preferred_language"])

            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                selected_language,
                max_age=60 * 60 * 24 * 365,
                path="/",
                secure=self.request.is_secure(),
                httponly=False,
                samesite="Lax",
            )

        try:
            from apps.audit.services import log_system_action

            from apps.audit.models.choices import ACTION_LOGIN, SEVERITY_SECURITY

            log_system_action(
                user=user,
                module="authentication",
                action="accounts.useraccount:login",
                action_type=ACTION_LOGIN,
                request=self.request,
                object_type="User account",
                object_id=user.pk,
                object_label=user.email,
                severity=SEVERITY_SECURITY,
            )
        except Exception:
            pass

        return response


class CRMLogoutView(LogoutView):
    next_page = reverse_lazy("login")
    # Logout is state-changing and must remain CSRF-protected. All bundled
    # templates already submit it through a POST form.
    http_method_names = ["post", "options"]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user and user.is_authenticated:
            try:
                from apps.audit.models.choices import ACTION_LOGOUT, SEVERITY_SECURITY
                from apps.audit.services import log_system_action

                log_system_action(
                    user=user,
                    module="authentication",
                    action="accounts.useraccount:logout",
                    action_type=ACTION_LOGOUT,
                    request=request,
                    object_type="User account",
                    object_id=user.pk,
                    object_label=user.email,
                    severity=SEVERITY_SECURITY,
                )
            except Exception:
                pass
        return super().post(request, *args, **kwargs)


def get_company_role_base_url(request, company_slug=None):
    active_slug = get_active_company_slug(request, company_slug)
    if active_slug:
        return f"/{active_slug}/roles/"
    return reverse("accounts:role_list")


def get_company_role_url(request, role=None, action=None, company_slug=None):
    base_url = get_company_role_base_url(request, company_slug)
    if role is None:
        return base_url
    url = f"{base_url}{role.id_role}/"
    if action:
        url = f"{url}{action.strip('/')}/"
    return url


def _role_filters_from_request(request):
    query = (request.GET.get("q") or "").strip()
    access_type = (request.GET.get("access") or "").strip().lower()
    order = (request.GET.get("order") or "name").strip().lower()

    if access_type not in {"", "standard", "contractor"}:
        access_type = ""
    if order not in {"name", "modules", "users"}:
        order = "name"

    return {
        "q": query,
        "access": access_type,
        "order": order,
    }


def _apply_role_filters(queryset, filters):
    query = filters.get("q") or ""
    access_type = filters.get("access") or ""

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
        )

    if access_type == "standard":
        queryset = queryset.filter(is_contractor_only=False)
    elif access_type == "contractor":
        queryset = queryset.filter(is_contractor_only=True)

    return queryset


def _annotate_role_queryset(queryset):
    return queryset.annotate(
        configured_modules_count=Count("permissions", distinct=True),
        view_modules_count=Count(
            "permissions",
            filter=Q(permissions__can_view=True),
            distinct=True,
        ),
        manage_modules_count=Count(
            "permissions",
            filter=(
                Q(permissions__can_create=True)
                | Q(permissions__can_edit=True)
                | Q(permissions__can_delete=True)
            ),
            distinct=True,
        ),
        approve_modules_count=Count(
            "permissions",
            filter=Q(permissions__can_approve=True),
            distinct=True,
        ),
        assigned_users_count=Count("users", distinct=True),
    )


class RoleListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "roles"
    permission_required = PERMISSION_VIEW
    template_name = "accounts/list.html"
    context_object_name = "roles"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        self.role_filters = _role_filters_from_request(self.request)
        queryset = role_list_for_user(self.request.user)
        queryset = _apply_role_filters(queryset, self.role_filters)
        queryset = _annotate_role_queryset(queryset)

        order = self.role_filters["order"]
        if order == "modules":
            return queryset.order_by("-configured_modules_count", "name")
        if order == "users":
            return queryset.order_by("-assigned_users_count", "name")
        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Roles"
        context["can_create_roles"] = user_can_module_action(
            self.request.user,
            "roles",
            PERMISSION_CREATE,
        )
        context["can_edit_roles"] = user_can_module_action(
            self.request.user,
            "roles",
            PERMISSION_EDIT,
        )
        context["can_manage_roles"] = context["can_edit_roles"]
        context["role_filters"] = self.role_filters
        context["role_list_url"] = get_company_role_base_url(
            self.request,
            self.kwargs.get("company_slug"),
        )
        context["role_create_url"] = f'{context["role_list_url"]}create/'

        visible_roles = context.get("roles") or []
        for role in visible_roles:
            role.detail_url = get_company_role_url(
                self.request,
                role,
                company_slug=self.kwargs.get("company_slug"),
            )
            role.edit_url = get_company_role_url(
                self.request,
                role,
                action="edit",
                company_slug=self.kwargs.get("company_slug"),
            )

        summary_queryset = role_list_for_user(self.request.user)
        summary_queryset = _apply_role_filters(summary_queryset, self.role_filters)
        context["role_summary"] = summary_queryset.aggregate(
            total=Count("id_role", distinct=True),
            standard=Count(
                "id_role",
                filter=Q(is_contractor_only=False),
                distinct=True,
            ),
            contractor=Count(
                "id_role",
                filter=Q(is_contractor_only=True),
                distinct=True,
            ),
            assigned_users=Count("users", distinct=True),
        )

        query_data = self.request.GET.copy()
        query_data.pop("page", None)
        context["role_filter_query"] = query_data.urlencode()
        return context


class RoleDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "roles"
    permission_required = PERMISSION_VIEW
    model = Role
    template_name = "accounts/detail.html"
    context_object_name = "role"
    pk_url_kwarg = "id_role"
    login_url = "/login/"

    def get_queryset(self):
        return _annotate_role_queryset(
            role_list_for_user(self.request.user).prefetch_related("permissions")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Role Details"
        context["can_edit_roles"] = user_can_module_action(
            self.request.user,
            "roles",
            PERMISSION_EDIT,
        )
        context["can_manage_roles"] = context["can_edit_roles"]
        context["permission_rows"] = get_permission_rows_for_role(
            self.request.user,
            self.object,
        )
        context["role_list_url"] = get_company_role_base_url(
            self.request,
            self.kwargs.get("company_slug"),
        )
        context["role_edit_url"] = get_company_role_url(
            self.request,
            self.object,
            action="edit",
            company_slug=self.kwargs.get("company_slug"),
        )
        return context


class RoleCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "roles"
    permission_required = PERMISSION_CREATE
    model = Role
    form_class = RoleForm
    template_name = "accounts/form.html"
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.id_company = self.request.user.id_company
        if not self.object.status:
            self.object.status = STATUS_ACTIVE
        self.object.save()

        allowed_modules = [
            module_value
            for module_value, _module_label in get_role_module_choices_for_user(
                self.request.user,
                role=self.object,
            )
        ]
        sync_role_permissions_from_post(
            role=self.object,
            allowed_modules=allowed_modules,
            post_data=self.request.POST,
        )
        messages.success(self.request, "Role and permissions created successfully.")
        return redirect_to_company_role_detail(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the highlighted role fields.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Role"
        context["form_title"] = "Create Role"
        context["submit_label"] = "Create role"
        context["show_permission_matrix"] = True
        context["permission_rows"] = get_permission_rows_for_role(
            self.request.user,
            None,
        )
        context["role_list_url"] = get_company_role_base_url(
            self.request,
            self.kwargs.get("company_slug"),
        )
        return context


class RoleUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "roles"
    permission_required = PERMISSION_EDIT
    model = Role
    form_class = RoleForm
    template_name = "accounts/form.html"
    context_object_name = "role"
    pk_url_kwarg = "id_role"
    login_url = "/login/"

    def get_queryset(self):
        return role_list_for_user(self.request.user).prefetch_related("permissions")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.id_company = self.request.user.id_company
        if not self.object.status:
            self.object.status = STATUS_ACTIVE
        self.object.save()

        allowed_modules = [
            module_value
            for module_value, _module_label in get_role_module_choices_for_user(
                self.request.user,
                role=self.object,
            )
        ]
        sync_role_permissions_from_post(
            role=self.object,
            allowed_modules=allowed_modules,
            post_data=self.request.POST,
        )
        messages.success(self.request, "Role and permissions updated successfully.")
        return redirect_to_company_role_detail(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the highlighted role fields.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Role"
        context["form_title"] = "Edit Role"
        context["submit_label"] = "Save changes"
        context["show_permission_matrix"] = True
        context["permission_rows"] = get_permission_rows_for_role(
            self.request.user,
            self.object,
        )
        context["role_list_url"] = get_company_role_base_url(
            self.request,
            self.kwargs.get("company_slug"),
        )
        context["role_detail_url"] = get_company_role_url(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )
        return context


class RolePermissionBulkUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    """Compatibility endpoint; role permissions now live in the unified edit screen."""

    module_name = "roles"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.role = role_get_for_user(request.user, self.kwargs.get("id_role"))
        if not self.role:
            return HttpResponseForbidden("Permission denied.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return redirect(
            get_company_role_url(
                request,
                self.role,
                action="edit",
                company_slug=self.kwargs.get("company_slug"),
            )
        )

    def post(self, request, *args, **kwargs):
        allowed_modules = [
            module_value
            for module_value, _module_label in get_role_module_choices_for_user(
                request.user,
                role=self.role,
            )
        ]
        sync_role_permissions_from_post(
            role=self.role,
            allowed_modules=allowed_modules,
            post_data=request.POST,
        )
        messages.success(request, "Role permissions updated successfully.")
        return redirect_to_company_role_detail(
            request,
            self.role,
            company_slug=self.kwargs.get("company_slug"),
        )


class RolePermissionCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    """Legacy compatibility route redirected to the unified roles screen."""

    module_name = "roles"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        messages.info(request, "Permissions are managed from the role edit screen.")
        return redirect_to_company_role_list(
            request,
            company_slug=self.kwargs.get("company_slug"),
        )

    post = get


class RolePermissionUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    """Legacy compatibility route redirected to the unified roles screen."""

    module_name = "roles"
    permission_required = PERMISSION_EDIT
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        messages.info(request, "Permissions are managed from the role edit screen.")
        return redirect_to_company_role_list(
            request,
            company_slug=self.kwargs.get("company_slug"),
        )

    post = get


class UserAccountListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "users"
    permission_required = PERMISSION_VIEW
    template_name = "accounts/user_account_list.html"
    context_object_name = "user_accounts"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        return user_account_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = getattr(self.request.user, "id_company", None)
        user_limit = get_company_user_limit(company)
        active_user_count = get_company_active_user_count(company)

        context["page_title"] = "Employees & Users"
        context["can_create_users"] = user_can_module_action(
            self.request.user,
            "users",
            PERMISSION_CREATE,
        )
        context["can_edit_users"] = user_can_module_action(
            self.request.user,
            "users",
            PERMISSION_EDIT,
        )
        context["company_user_limit"] = user_limit
        context["company_active_user_count"] = active_user_count
        context["company_user_slots_left"] = max(user_limit - active_user_count, 0) if user_limit else None
        context["company_user_limit_reached"] = company_active_user_limit_reached(company)

        return context


class UserAccountDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "users"
    permission_required = PERMISSION_VIEW
    model = UserAccount
    template_name = "accounts/user_account_detail.html"
    context_object_name = "user_account"
    pk_url_kwarg = "id_user"
    login_url = "/login/"

    def get_queryset(self):
        return user_account_list_for_user(self.request.user).select_related(
            "id_company",
            "id_role",
            "employee_profile",
        ).prefetch_related(
            "id_role__permissions",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Employee & User Details"
        context["can_edit_users"] = user_can_module_action(
            self.request.user,
            "users",
            PERMISSION_EDIT,
        )
        return context


class UserAccountCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "users"
    permission_required = PERMISSION_CREATE
    model = UserAccount
    form_class = UserAccountCreateForm
    template_name = "accounts/user_account_form.html"
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("accounts:user_account_list")

    def form_valid(self, form):
        self.object = form.save()

        messages.success(self.request, "Employee and user created successfully.")
        return redirect_to_company_user_list(
            self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the user form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = getattr(self.request.user, "id_company", None)
        user_limit = get_company_user_limit(company)
        active_user_count = get_company_active_user_count(company)

        context["page_title"] = "Create Employee & User"
        context["form_title"] = "Create Employee & User"
        context["submit_label"] = "Save Employee"
        context["is_create_form"] = True
        context["company_user_limit"] = user_limit
        context["company_active_user_count"] = active_user_count
        context["company_user_slots_left"] = max(user_limit - active_user_count, 0) if user_limit else None
        context["company_user_limit_reached"] = company_active_user_limit_reached(company)

        return context


class UserAccountUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "users"
    permission_required = PERMISSION_EDIT
    model = UserAccount
    form_class = UserAccountUpdateForm
    template_name = "accounts/user_account_form.html"
    context_object_name = "user_account"
    pk_url_kwarg = "id_user"
    login_url = "/login/"

    def get_queryset(self):
        return user_account_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("accounts:user_account_list")

    def form_valid(self, form):
        self.object = form.save()

        messages.success(self.request, "Employee and user updated successfully.")
        return redirect_to_company_user_list(
            self.request,
            company_slug=self.kwargs.get("company_slug"),
        )

    def form_invalid(self, form):
        messages.error(self.request, "Please review the employee and user form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Employee & User"
        context["form_title"] = "Edit Employee & User"
        context["submit_label"] = "Save Changes"
        context["is_create_form"] = False
        return context


def user_account_activate_view(request, id_user, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "users",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    user_account = get_object_or_404(
        user_account_list_for_user(request.user),
        id_user=id_user,
    )

    if request.method != "POST":
        messages.error(request, "Use the Activate button to enable a user account.")
        return redirect_to_company_user_detail(
            request,
            user_account,
            company_slug=company_slug,
        )

    company = getattr(user_account, "id_company", None)

    if not user_account.is_active and company_active_user_limit_reached(company):
        messages.error(request, get_company_user_limit_message(company))
        return redirect_to_company_user_detail(
            request,
            user_account,
            company_slug=company_slug,
        )

    user_account_activate(user_account)

    messages.success(request, "User activated successfully.")
    return redirect_to_company_user_list(request, company_slug=company_slug)


def user_account_deactivate_view(request, id_user, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "users",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    user_account = get_object_or_404(
        user_account_list_for_user(request.user),
        id_user=id_user,
    )

    if request.method != "POST":
        messages.error(request, "Use the Deactivate button to disable a user account.")
        return redirect_to_company_user_detail(
            request,
            user_account,
            company_slug=company_slug,
        )

    if request.user.id_user == user_account.id_user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect_to_company_user_detail(
            request,
            user_account,
            company_slug=company_slug,
        )

    user_account_deactivate(user_account)

    messages.success(request, "User deactivated successfully.")
    return redirect_to_company_user_list(request, company_slug=company_slug)


class RoleViewSet(TenantModelViewSet):
    module_name = "roles"
    queryset = Role.objects.select_related("id_company").all()
    serializer_class = RoleSerializer
    tenant_filter_path = "id_company"


class RolePermissionViewSet(viewsets.ModelViewSet):
    module_name = "roles"
    queryset = RolePermission.objects.select_related(
        "id_role",
        "id_role__id_company",
    ).all()
    serializer_class = RolePermissionSerializer
    permission_classes = [HasModulePermission]

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.request.user.is_superuser:
            return queryset

        return queryset.filter(id_role__id_company=self.request.user.id_company)


class UserAccountViewSet(TenantModelViewSet):
    module_name = "users"
    queryset = UserAccount.objects.select_related(
        "id_company",
        "id_role",
    ).all()
    serializer_class = UserAccountSerializer
    tenant_filter_path = "id_company"


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return Response(
            {
                "id": user.id_user,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "company_id": user.id_company_id,
                "company_name": user.id_company.name if user.id_company_id else None,
                "role_id": user.id_role_id,
                "role_name": user.id_role.name if user.id_role_id else None,
                "is_superuser": user.is_superuser,
            }
        )