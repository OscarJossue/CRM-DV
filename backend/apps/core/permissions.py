from rest_framework.permissions import BasePermission

MODULE_PERMISSION_ALIASES = {
    # Employee pages are legacy redirects. Access is controlled by the unified
    # Employees & Users permission so old URLs and dashboard checks keep working.
    "employees": "users",
}


ACTION_PERMISSION_MAP = {
    "list": "can_view",
    "retrieve": "can_view",
    "create": "can_create",
    "update": "can_edit",
    "partial_update": "can_edit",
    "destroy": "can_delete",
    "send": "can_edit",
    "generate": "can_edit",
    "mark_sent": "can_edit",
    "mark_paid": "can_edit",
    "mark_pending": "can_edit",
    "approve": "can_approve",
    "verify": "can_approve",
    "confirm": "can_approve",
    "reject": "can_approve",
    "cancel": "can_approve",
    "complete": "can_approve",
    "final_audit": "can_approve",
    "void": "can_approve",
    "mark_signed": "can_approve",
}


def user_has_module_permission(user, module_name, permission_field="can_view"):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if not module_name:
        return True

    module_name = MODULE_PERMISSION_ALIASES.get(module_name, module_name)

    # Tenant users can never receive platform-administration permissions from
    # a company role, including company owners.
    if module_name.startswith("platform_"):
        return False

    company = getattr(user, "id_company", None)

    try:
        from apps.company_modules.selectors import company_has_module_enabled

        if not company_has_module_enabled(company, module_name):
            return False
    except Exception:
        pass

    # The company owner is the tenant administrator. An old or partially
    # imported Owner role must not lock the owner out of their own active
    # workspace. Module enable/disable rules above still apply.
    if getattr(user, "is_company_owner", False):
        return True

    role = getattr(user, "id_role", None)

    if not role:
        return False

    if getattr(role, "status", "active") != "active":
        return False

    return role.permissions.filter(
        module=module_name,
        **{permission_field: True},
    ).exists()


class HasModulePermission(BasePermission):
    """Checks role permissions and company module availability."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        module_name = getattr(view, "module_name", None)

        if not module_name:
            return True

        permission_field = ACTION_PERMISSION_MAP.get(
            getattr(view, "action", "list"),
            "can_view",
        )

        return user_has_module_permission(
            request.user,
            module_name,
            permission_field,
        )
