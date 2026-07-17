from .models import Role, RolePermission, UserAccount


def role_list_for_user(user):
    queryset = Role.objects.select_related("id_company").all().order_by(
        "id_company__name",
        "name",
    )

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def role_get_for_user(user, id_role):
    return role_list_for_user(user).filter(id_role=id_role).first()


def role_permission_list_for_user(user):
    queryset = RolePermission.objects.select_related(
        "id_role",
        "id_role__id_company",
    ).all().order_by(
        "id_role__name",
        "module",
    )

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_role__id_company=user.id_company_id)


def role_permission_get_for_user(user, id_permission):
    return role_permission_list_for_user(user).filter(
        id_permission=id_permission
    ).first()


def user_account_list_for_user(user):
    queryset = UserAccount.objects.select_related(
        "id_company",
        "id_role",
        "employee_profile",
    ).all().order_by(
        "first_name",
        "last_name",
    )

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def user_account_get_for_user(user, id_user):
    return user_account_list_for_user(user).filter(id_user=id_user).first()


def user_account_get_by_id(id_user):
    return UserAccount.objects.filter(id_user=id_user).first()
