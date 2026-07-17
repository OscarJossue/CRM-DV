from apps.core.permissions import HasModulePermission


class ContractPermission(HasModulePermission):
    pass


def user_can_access_contract(user, contract):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    user_company_id = getattr(user, "id_company_id", None)

    if not user_company_id:
        return False

    if contract.id_company_id and contract.id_company_id == user_company_id:
        return True

    if contract.id_project_id and contract.id_project.id_company_id == user_company_id:
        return True

    if contract.id_client_id and contract.id_client.id_company_id == user_company_id:
        return True

    return False