from apps.core.permissions import HasModulePermission


class SupervisionPermission(HasModulePermission):
    pass


def user_can_access_supervision(user, supervision):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return supervision.company_id == user.id_company_id
