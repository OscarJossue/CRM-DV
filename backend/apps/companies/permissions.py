from apps.core.permissions import HasModulePermission


def user_can_manage_companies(user):
    if not user or not user.is_authenticated:
        return False

    return user.is_superuser


def user_can_access_company(user, company):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return getattr(user, "id_company_id", None) == getattr(company, "id_company", None)


class CompanyPermission(HasModulePermission):
    pass
