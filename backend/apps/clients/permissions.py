from apps.core.permissions import HasModulePermission


class ClientPermission(HasModulePermission):
    pass


def user_can_access_client(user, client):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return client.id_company_id == user.id_company_id