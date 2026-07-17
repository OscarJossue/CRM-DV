from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from apps.platform_users.models import PlatformUserPermission


PERMISSION_VIEW = "view"
PERMISSION_CREATE = "create"
PERMISSION_EDIT = "edit"
PERMISSION_DELETE = "delete"
PERMISSION_APPROVE = "approve"


def user_is_platform_root(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_superuser
    )


def user_is_platform_staff(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_staff
        and not user.is_superuser
        and user.is_active
        and getattr(user, "status", None) == "active"
    )


def user_can_access_platform(user):
    return user_is_platform_root(user) or user_is_platform_staff(user)


def user_can_platform_action(user, module_name, action=PERMISSION_VIEW):
    if user_is_platform_root(user):
        return True

    if not user_is_platform_staff(user):
        return False

    permission = PlatformUserPermission.objects.filter(
        id_user=user,
        module=module_name,
    ).first()

    if not permission:
        return False

    if action == PERMISSION_VIEW:
        return permission.can_view

    if action == PERMISSION_CREATE:
        return permission.can_create

    if action == PERMISSION_EDIT:
        return permission.can_edit

    if action == PERMISSION_DELETE:
        return permission.can_delete

    if action == PERMISSION_APPROVE:
        return permission.can_approve

    return False


def require_platform_action(user, module_name, action=PERMISSION_VIEW):
    if not user_can_platform_action(user, module_name, action):
        raise PermissionDenied("You do not have permission to access this platform module.")

    return True


class PlatformPermissionRequiredMixin(UserPassesTestMixin):
    login_url = "/login/"
    raise_exception = True
    platform_module_name = None
    platform_permission_required = PERMISSION_VIEW

    def test_func(self):
        if not self.platform_module_name:
            return user_is_platform_root(self.request.user)

        return user_can_platform_action(
            self.request.user,
            self.platform_module_name,
            self.platform_permission_required,
        )