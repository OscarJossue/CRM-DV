from apps.core.permissions import HasModulePermission, user_has_module_permission


def user_can_manage_employees(user):
    return user_has_module_permission(user, "users", "can_edit")


def user_can_access_employee(user, employee):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, "id_company_id", None) == getattr(employee, "id_company_id", None)


class EmployeePermission(HasModulePermission):
    pass
