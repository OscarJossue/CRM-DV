from apps.core.permissions import HasModulePermission


class EstimatePermission(HasModulePermission):
    pass


def user_can_access_estimate(user, estimate):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return estimate.id_company_id == user.id_company_id
