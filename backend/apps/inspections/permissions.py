from apps.core.permissions import HasModulePermission


class InspectionPermission(HasModulePermission):
    pass


def user_can_access_inspection(user, inspection):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if not user.id_company_id:
        return False

    return inspection.id_project.id_company_id == user.id_company_id