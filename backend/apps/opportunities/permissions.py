from apps.core.permissions import HasModulePermission


class LeadPermission(HasModulePermission):
    pass


def user_can_access_lead(user, lead):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return lead.id_company_id == user.id_company_id