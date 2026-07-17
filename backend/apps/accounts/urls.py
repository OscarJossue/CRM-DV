from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy
from .forms import CRMPasswordResetForm

from .views import (
    CRMLoginView,
    CRMLogoutView,
    RoleCreateView,
    RoleDetailView,
    RoleListView,
    RolePermissionBulkUpdateView,
    RolePermissionCreateView,
    RolePermissionUpdateView,
    RoleUpdateView,
    UserAccountCreateView,
    UserAccountDetailView,
    UserAccountListView,
    UserAccountUpdateView,
    user_account_activate_view,
    user_account_deactivate_view,
)

app_name = "accounts"

urlpatterns = [
    path("login/", CRMLoginView.as_view(), name="login"),
    path("logout/", CRMLogoutView.as_view(), name="logout"),

    path(
        "password-reset/",
        PasswordResetView.as_view(
            form_class=CRMPasswordResetForm,
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    path("roles/", RoleListView.as_view(), name="role_list"),
    path("roles/create/", RoleCreateView.as_view(), name="role_create"),
    path("roles/<int:id_role>/", RoleDetailView.as_view(), name="role_detail"),
    path("roles/<int:id_role>/edit/", RoleUpdateView.as_view(), name="role_update"),
    path(
        "roles/<int:id_role>/permissions/",
        RolePermissionBulkUpdateView.as_view(),
        name="role_permission_bulk_update",
    ),
    path(
        "roles/<int:id_role>/permissions/create/",
        RolePermissionCreateView.as_view(),
        name="role_permission_create",
    ),
    path(
        "permissions/<int:id_permission>/edit/",
        RolePermissionUpdateView.as_view(),
        name="role_permission_update",
    ),

    path("users/", UserAccountListView.as_view(), name="user_account_list"),
    path("users/create/", UserAccountCreateView.as_view(), name="user_account_create"),
    path("users/<int:id_user>/", UserAccountDetailView.as_view(), name="user_account_detail"),
    path("users/<int:id_user>/edit/", UserAccountUpdateView.as_view(), name="user_account_update"),
    path("users/<int:id_user>/activate/", user_account_activate_view, name="user_account_activate"),
    path("users/<int:id_user>/deactivate/", user_account_deactivate_view, name="user_account_deactivate"),
]