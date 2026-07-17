from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.models import UserAccount

from .constants import PLATFORM_MODULE_CHOICES, PLATFORM_PERMISSION_ACTIONS
from .forms import PlatformUserCreateForm, PlatformUserUpdateForm
from .models import PlatformUserPermission


class PlatformRootRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "/login/"
    raise_exception = True

    def test_func(self):
        return bool(
            self.request.user
            and self.request.user.is_authenticated
            and self.request.user.is_superuser
        )


def get_permission_rows(platform_user=None, post_data=None):
    permission_map = {}

    if platform_user and platform_user.pk:
        permission_map = {
            permission.module: permission
            for permission in PlatformUserPermission.objects.filter(id_user=platform_user)
        }

    rows = []

    for module_value, module_label in PLATFORM_MODULE_CHOICES:
        permission = permission_map.get(module_value)

        row = {
            "module": module_value,
            "module_label": module_label,
            "actions": [],
        }

        for action_key, action_label in PLATFORM_PERMISSION_ACTIONS:
            field_name = f"{module_value}_{action_key}"

            if post_data is not None:
                checked = post_data.get(field_name) == "on"
            elif permission:
                checked = bool(getattr(permission, action_key))
            else:
                checked = module_value == "platform_dashboard" and action_key == "can_view"

            row["actions"].append(
                {
                    "key": action_key,
                    "label": action_label,
                    "field_name": field_name,
                    "checked": checked,
                }
            )

        rows.append(row)

    return rows


def save_platform_permissions(platform_user, post_data):
    for module_value, module_label in PLATFORM_MODULE_CHOICES:
        can_view = post_data.get(f"{module_value}_can_view") == "on"
        can_create = post_data.get(f"{module_value}_can_create") == "on"
        can_edit = post_data.get(f"{module_value}_can_edit") == "on"
        can_delete = post_data.get(f"{module_value}_can_delete") == "on"
        can_approve = post_data.get(f"{module_value}_can_approve") == "on"

        if can_create or can_edit or can_delete or can_approve:
            can_view = True

        PlatformUserPermission.objects.update_or_create(
            id_user=platform_user,
            module=module_value,
            defaults={
                "can_view": can_view,
                "can_create": can_create,
                "can_edit": can_edit,
                "can_delete": can_delete,
                "can_approve": can_approve,
            },
        )


class PlatformUserListView(PlatformRootRequiredMixin, ListView):
    template_name = "platform_users/list.html"
    context_object_name = "platform_users"
    paginate_by = 20

    def get_queryset(self):
        return UserAccount.objects.prefetch_related(
            "platform_permissions",
        ).filter(
            id_company__isnull=True,
            is_staff=True,
            is_superuser=False,
        ).order_by("first_name", "last_name", "email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Platform Users"
        return context


class PlatformUserDetailView(PlatformRootRequiredMixin, DetailView):
    model = UserAccount
    template_name = "platform_users/detail.html"
    context_object_name = "platform_user"
    pk_url_kwarg = "id_user"

    def get_queryset(self):
        return UserAccount.objects.prefetch_related(
            "platform_permissions",
        ).filter(
            id_company__isnull=True,
            is_staff=True,
            is_superuser=False,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Platform User Details"
        context["permission_rows"] = get_permission_rows(platform_user=self.object)
        return context


class PlatformUserCreateView(PlatformRootRequiredMixin, CreateView):
    model = UserAccount
    form_class = PlatformUserCreateForm
    template_name = "platform_users/form.html"
    success_url = reverse_lazy("platform_users:user_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Create Platform User"
        context["form_title"] = "Create Platform User"
        context["submit_label"] = "Save Platform User"

        if self.request.method == "POST":
            context["permission_rows"] = get_permission_rows(post_data=self.request.POST)
        else:
            context["permission_rows"] = get_permission_rows()

        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            save_platform_permissions(self.object, self.request.POST)

        messages.success(self.request, "Platform user created successfully.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform user form.")
        return super().form_invalid(form)


class PlatformUserUpdateView(PlatformRootRequiredMixin, UpdateView):
    model = UserAccount
    form_class = PlatformUserUpdateForm
    template_name = "platform_users/form.html"
    context_object_name = "platform_user"
    pk_url_kwarg = "id_user"

    def get_queryset(self):
        return UserAccount.objects.prefetch_related(
            "platform_permissions",
        ).filter(
            id_company__isnull=True,
            is_staff=True,
            is_superuser=False,
        )

    def get_success_url(self):
        return reverse_lazy(
            "platform_users:user_detail",
            kwargs={"id_user": self.object.id_user},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Edit Platform User"
        context["form_title"] = "Edit Platform User"
        context["submit_label"] = "Update Platform User"

        if self.request.method == "POST":
            context["permission_rows"] = get_permission_rows(
                platform_user=self.object,
                post_data=self.request.POST,
            )
        else:
            context["permission_rows"] = get_permission_rows(platform_user=self.object)

        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            save_platform_permissions(self.object, self.request.POST)

        messages.success(self.request, "Platform user updated successfully.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform user form.")
        return super().form_invalid(form)