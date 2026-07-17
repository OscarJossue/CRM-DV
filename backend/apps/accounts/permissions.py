from apps.core.permissions import HasModulePermission


def user_can_manage_roles(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = getattr(user, "id_role", None)

    if not role:
        return False

    return role.permissions.filter(
        module="roles",
        can_edit=True,
    ).exists()


def user_can_access_role(user, role):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return getattr(user, "id_company_id", None) == getattr(role, "id_company_id", None)


def user_can_access_role_permission(user, role_permission):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return getattr(user, "id_company_id", None) == getattr(
        role_permission.id_role,
        "id_company_id",
        None,
    )


def user_can_manage_users(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = getattr(user, "id_role", None)

    if not role:
        return False

    return role.permissions.filter(
        module="users",
        can_edit=True,
    ).exists()


def user_can_access_user_account(user, user_account):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return getattr(user, "id_company_id", None) == getattr(
        user_account,
        "id_company_id",
        None,
    )


class UserAccountPermission(HasModulePermission):
    pass


class RolePermission(HasModulePermission):
    pass
