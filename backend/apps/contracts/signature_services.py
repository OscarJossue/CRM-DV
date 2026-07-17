import base64
import binascii
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.contracts.models.choices import (
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_SIGNED,
)


class ContractSignatureError(Exception):
    pass


def _decode_signature_data(signature_data):
    if not signature_data or len(signature_data) > 2_000_000:
        raise ContractSignatureError("Signature is missing or too large.")

    allowed_prefixes = {
        "data:image/png": "png",
        "data:image/jpeg": "jpg",
    }
    if ";base64," not in signature_data:
        raise ContractSignatureError("Invalid signature format.")

    format_part, image_string = signature_data.split(";base64,", 1)
    extension = allowed_prefixes.get(format_part)
    if not extension:
        raise ContractSignatureError("Only PNG or JPEG signatures are accepted.")

    try:
        decoded = base64.b64decode(image_string, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ContractSignatureError("Could not process signature image.") from exc

    if not decoded or len(decoded) > 1_000_000:
        raise ContractSignatureError("Signature image exceeds the 1 MB limit.")

    if extension == "png" and not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ContractSignatureError("Invalid PNG signature data.")
    if extension == "jpg" and not decoded.startswith(b"\xff\xd8\xff"):
        raise ContractSignatureError("Invalid JPEG signature data.")

    return extension, decoded


def can_sign_contract(contract):
    return contract.status == CONTRACT_STATUS_APPROVED


@transaction.atomic
def sign_contract_publicly(contract, signature_data, sign_token):
    from apps.contracts.models import Contract
    contract = Contract.objects.select_for_update().get(pk=contract.pk)

    if str(contract.sign_token) != str(sign_token):
        raise ContractSignatureError("Invalid or expired signature link.")
    if contract.sign_token_used_at:
        raise ContractSignatureError("This signature link has already been used.")
    if contract.sign_token_expires_at and contract.sign_token_expires_at < timezone.now():
        raise ContractSignatureError("This signature link has expired.")
    if not can_sign_contract(contract):
        raise ContractSignatureError("This contract must be approved before signing.")

    extension, decoded_image = _decode_signature_data(signature_data)

    file_name = f"contract_signature_{contract.id_contract}_{uuid.uuid4().hex}.{extension}"

    contract.signature_image.save(
        file_name,
        ContentFile(decoded_image),
        save=False,
    )

    contract.status = CONTRACT_STATUS_SIGNED
    contract.sign_token_used_at = timezone.now()

    contract.save(
        update_fields=[
            "signature_image",
            "status",
            "sign_token_used_at",
            "updated_at",
        ]
    )

    return contract