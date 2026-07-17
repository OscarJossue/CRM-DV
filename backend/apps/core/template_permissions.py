from django.http import HttpResponseForbidden

from apps.core.permissions import user_has_module_permission

PERMISSION_VIEW = "can_view"
PERMISSION_CREATE = "can_create"
PERMISSION_EDIT = "can_edit"
PERMISSION_DELETE = "can_delete"
PERMISSION_APPROVE = "can_approve"


def user_can_module_action(user, module_name, permission):
    return user_has_module_permission(
        user,
        module_name,
        permission,
    )


def require_module_action_or_403(user, module_name, permission):
    if not user_can_module_action(user, module_name, permission):
        return HttpResponseForbidden("Permission denied.")

    return None


class ModulePermissionRequiredMixin:
    module_name = None
    permission_required = PERMISSION_VIEW

    def dispatch(self, request, *args, **kwargs):
        if not user_can_module_action(
            request.user,
            self.module_name,
            self.permission_required,
        ):
            return HttpResponseForbidden("Permission denied.")

        return super().dispatch(request, *args, **kwargs)
