from apps.core.permissions import HasModulePermission


class SystemLogPermission(HasModulePermission):
    pass


def user_can_access_system_log(user, system_log):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return system_log.id_company_id == user.id_company_id
