from django.db.models import Q

from apps.accounts.models import RolePermission, UserAccount
from apps.notifications.models import Notification

try:
    from apps.notifications.models.choices import (
        NOTIFICATION_STATUS_UNREAD,
        NOTIFICATION_TYPE_CONTRACT,
    )
except Exception:
    NOTIFICATION_STATUS_UNREAD = "unread"
    NOTIFICATION_TYPE_CONTRACT = "contract"


CONTRACTS_MODULE_NAME = "contracts"


def get_users_with_contracts_access(company):
    """
    Return active users from the same company whose role has access
    to the contracts module.

    This is used for bell notifications when a contract is approved,
    rejected, signed, or needs attention.
    """
    if not company:
        return UserAccount.objects.none()

    role_ids = (
        RolePermission.objects.filter(
            module=CONTRACTS_MODULE_NAME,
        )
        .filter(
            Q(can_view=True)
            | Q(can_create=True)
            | Q(can_edit=True)
            | Q(can_delete=True)
            | Q(can_approve=True)
        )
        .values_list("id_role", flat=True)
        .distinct()
    )

    return (
        UserAccount.objects.filter(
            id_company=company,
            id_role__in=role_ids,
            is_active=True,
        )
        .distinct()
    )


def create_contract_notification(user, title, message):
    """
    Create one bell notification for a user.
    """
    if not user:
        return None

    return Notification.objects.create(
        id_user=user,
        type=NOTIFICATION_TYPE_CONTRACT,
        title=title,
        message=message,
        status=NOTIFICATION_STATUS_UNREAD,
    )


def notify_contract_rejected_to_contract_users(contract):
    """
    Notify all users with access to the contracts module that a contract
    was rejected by the client.
    """
    company = contract.id_company
    contract_number = contract.contract_number or f"Contract {contract.id_contract}"
    client_name = contract.client_name or getattr(contract.id_client, "name", "") or "Client"
    project_name = contract.project_name or getattr(contract.id_project, "project_name", "") or "Project"
    reason = contract.rejection_reason or "No rejection reason provided."

    title = "Contract Rejected"
    message = (
        f"{contract_number} was rejected by {client_name}. "
        f"Project: {project_name}. "
        f"Reason: {reason}"
    )

    notifications = []
    users = get_users_with_contracts_access(company)

    for user in users:
        notification = create_contract_notification(
            user=user,
            title=title,
            message=message,
        )
        if notification:
            notifications.append(notification)

    return notifications


def notify_contract_approved_to_contract_users(contract):
    """
    Notify all users with access to the contracts module that a contract
    was approved by the client.
    """
    company = contract.id_company
    contract_number = contract.contract_number or f"Contract {contract.id_contract}"
    client_name = contract.client_name or getattr(contract.id_client, "name", "") or "Client"
    project_name = contract.project_name or getattr(contract.id_project, "project_name", "") or "Project"

    title = "Contract Approved"
    message = (
        f"{contract_number} was approved by {client_name}. "
        f"Project: {project_name}."
    )

    notifications = []
    users = get_users_with_contracts_access(company)

    for user in users:
        notification = create_contract_notification(
            user=user,
            title=title,
            message=message,
        )
        if notification:
            notifications.append(notification)

    return notifications


def notify_contract_signed_to_contract_users(contract):
    """
    Notify all users with access to the contracts module that a contract
    was signed by the client.
    """
    company = contract.id_company
    contract_number = contract.contract_number or f"Contract {contract.id_contract}"
    client_name = contract.client_name or getattr(contract.id_client, "name", "") or "Client"
    project_name = contract.project_name or getattr(contract.id_project, "project_name", "") or "Project"

    title = "Contract Signed"
    message = (
        f"{contract_number} was signed by {client_name}. "
        f"Project: {project_name}."
    )

    notifications = []
    users = get_users_with_contracts_access(company)

    for user in users:
        notification = create_contract_notification(
            user=user,
            title=title,
            message=message,
        )
        if notification:
            notifications.append(notification)

    return notifications