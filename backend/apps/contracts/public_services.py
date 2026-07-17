from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.contracts.models import Contract
from apps.contracts.models.choices import (
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_REJECTED,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_VIEWED,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_VOID,
)

from apps.contracts.notification_services import (
    notify_contract_approved_to_contract_users,
    notify_contract_rejected_to_contract_users,
)


PUBLIC_DECISION_ALLOWED_STATUSES = [
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_VIEWED,
]


PUBLIC_FINAL_STATUSES = [
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_REJECTED,
    CONTRACT_STATUS_VOID,
]


class ContractPublicFlowError(Exception):
    pass


def get_public_contract_by_token(token):
    """
    Get contract by public token.
    This is used by public customer pages without login.
    """
    try:
        return Contract.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_estimate",
        ).get(public_token=token)
    except Contract.DoesNotExist as exc:
        raise Http404("Contract review link not found.") from exc


def mark_contract_as_viewed(contract):
    from django.utils import timezone

    from apps.contracts.models.choices import (
        CONTRACT_STATUS_SENT,
        CONTRACT_STATUS_VIEWED,
    )

    if contract.status != CONTRACT_STATUS_SENT:
        return contract

    contract.status = CONTRACT_STATUS_VIEWED
    contract.viewed_at = timezone.now()
    contract.save(
        update_fields=[
            "status",
            "viewed_at",
            "updated_at",
        ]
    )

    return contract


def can_customer_decide_contract(contract):
    """
    Customer can approve/reject only while contract is sent or viewed.
    """
    if contract.expiration_date and contract.expiration_date < timezone.localdate():
        return False
    return contract.status in PUBLIC_DECISION_ALLOWED_STATUSES


@transaction.atomic
def approve_contract_publicly(contract):
    """
    Approve contract from public customer flow.
    Does not require CRM login.
    """
    contract = Contract.objects.select_for_update().get(pk=contract.pk)

    if not can_customer_decide_contract(contract):
        raise ContractPublicFlowError(
            "This contract can no longer be approved."
        )

    now = timezone.now()

    contract.status = CONTRACT_STATUS_APPROVED
    contract.approved_at = now
    contract.save(
        update_fields=[
            "status",
            "approved_at",
            "updated_at",
            "last_modified_at",
        ]
    )


    return contract


@transaction.atomic
def reject_contract_publicly(contract, reason):
    """
    Reject contract from public customer flow.
    A rejection reason is required.
    """
    contract = Contract.objects.select_for_update().get(pk=contract.pk)

    reason = (reason or "").strip()

    if not reason:
        raise ContractPublicFlowError(
            "A rejection reason is required."
        )

    if not can_customer_decide_contract(contract):
        raise ContractPublicFlowError(
            "This contract can no longer be rejected."
        )

    now = timezone.now()

    contract.status = CONTRACT_STATUS_REJECTED
    contract.rejected_at = now
    contract.rejection_reason = reason
    contract.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "updated_at",
            "last_modified_at",
        ]
    )


    return contract