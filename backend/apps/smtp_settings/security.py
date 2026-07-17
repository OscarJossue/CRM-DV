"""Encryption helpers for reversible company SMTP credentials.

Company SMTP passwords cannot be hashed because the CRM must present them to
an SMTP server. They are therefore encrypted at rest with a dedicated Fernet
key. Login passwords remain one-way Django password hashes and never use this
module.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


ENCRYPTED_PREFIX = "fernet:v1:"


class CredentialDecryptionError(ValueError):
    """Raised when an encrypted credential cannot be opened with the current key."""


def _normalize_fernet_key(raw_key: str) -> bytes:
    value = (raw_key or "").strip()
    if value:
        try:
            decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
            if len(decoded) == 32:
                return value.encode("utf-8")
        except Exception:
            pass

    # Development compatibility for arbitrary local secrets. Production
    # settings require a separate high-entropy key before Django starts.
    digest = hashlib.sha256(
        value.encode("utf-8") or settings.SECRET_KEY.encode("utf-8")
    ).digest()
    return base64.urlsafe_b64encode(digest)


def get_credential_fernet() -> Fernet:
    configured_key = getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "")
    return Fernet(_normalize_fernet_key(configured_key))


def is_encrypted_smtp_password(value: str | None) -> bool:
    return bool(value and str(value).startswith(ENCRYPTED_PREFIX))


def encrypt_smtp_password(value: str | None) -> str:
    if value in (None, ""):
        return ""

    value = str(value)
    if is_encrypted_smtp_password(value):
        return value

    token = get_credential_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_smtp_password(value: str | None) -> str:
    if not value:
        return ""

    value = str(value)
    if not is_encrypted_smtp_password(value):
        # Backward-compatible read of legacy plaintext rows. Run the bundled
        # encrypt_smtp_credentials command to convert them in place.
        return value

    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        return get_credential_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise CredentialDecryptionError(
            "The saved SMTP password cannot be decrypted with the configured credential key."
        ) from exc
