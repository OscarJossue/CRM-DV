from apps.core.permissions import HasModulePermission


class CompanyModulePermission(HasModulePermission):
    pass


def user_can_manage_company_modules(user):
    return bool(user and user.is_authenticated and user.is_superuser)


def user_can_access_company_module(user, company_module):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return company_module.id_company_id == user.id_company_id
