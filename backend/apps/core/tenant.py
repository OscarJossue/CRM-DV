from django.core.exceptions import PermissionDenied


def user_is_global_admin(user):
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
    )


def user_can_access_crm_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
        )
    )


def get_user_company(user):
    if not user or not user.is_authenticated:
        return None

    return getattr(user, "id_company", None)


def get_active_tenant_company(user):
    if user_is_global_admin(user):
        return None

    return get_user_company(user)


def filter_queryset_for_user(queryset, user, company_field="id_company"):
    if not user or not user.is_authenticated:
        return queryset.none()

    if user_is_global_admin(user):
        return queryset

    company = get_user_company(user)

    if not company:
        return queryset.none()

    if not company_field:
        return queryset

    return queryset.filter(**{company_field: company})


def object_belongs_to_user_company(user, obj, company_field="id_company"):
    if not user or not user.is_authenticated:
        return False

    if user_is_global_admin(user):
        return True

    company = get_user_company(user)

    if not company:
        return False

    object_company_id = getattr(obj, f"{company_field}_id", None)

    if object_company_id:
        return object_company_id == company.id_company

    object_company = getattr(obj, company_field, None)

    return object_company == company


def require_object_company_access(user, obj, company_field="id_company"):
    if not object_belongs_to_user_company(user, obj, company_field):
        raise PermissionDenied("You do not have access to this company data.")

    return True


def assign_company_to_instance(user, instance, company_field="id_company"):
    if user_is_global_admin(user):
        return instance

    company = get_user_company(user)

    if not company:
        raise PermissionDenied("User does not have a company assigned.")

    setattr(instance, company_field, company)

    return instance