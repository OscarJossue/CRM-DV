"""Encryption helpers for integrations.

All sensitive integration fields are encrypted at rest using Fernet.
The key is read from INTEGRATION_ENCRYPTION_KEY when present, otherwise
it is deterministically derived from Django SECRET_KEY so local installs work
without extra setup. For production, define INTEGRATION_ENCRYPTION_KEY and
keep it outside git.
"""

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core import signing


def _normalize_fernet_key(raw_key: str) -> bytes:
    value = (raw_key or "").strip()
    if value:
        try:
            decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
            if len(decoded) == 32:
                return value.encode("utf-8")
        except Exception:
            pass
    digest = hashlib.sha256(value.encode("utf-8") or settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    configured_key = (getattr(settings, "INTEGRATION_ENCRYPTION_KEY", "") or "").strip()
    if not configured_key:
        if not getattr(settings, "DEBUG", False):
            raise RuntimeError("INTEGRATION_ENCRYPTION_KEY is required outside DEBUG mode.")
        configured_key = getattr(settings, "SECRET_KEY", "")
    return Fernet(_normalize_fernet_key(configured_key))


def encrypt_text(value: str | None) -> str:
    if value in (None, ""):
        return ""
    return get_fernet().encrypt(str(value).encode("utf-8")).decode("utf-8")


def decrypt_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Backward compatibility with the first integrations version, which used signing.
        try:
            loaded = signing.loads(value)
            if isinstance(loaded, dict):
                if "value" in loaded:
                    return str(loaded.get("value") or "")
                if "refresh_token" in loaded:
                    return str(loaded.get("refresh_token") or "")
            return str(loaded or "")
        except Exception:
            return ""


def encrypt_json(data: Any) -> str:
    return encrypt_text(json.dumps(data or {}, separators=(",", ":"), default=str))


def decrypt_json(value: str | None) -> dict:
    if not value:
        return {}
    decrypted = ""
    try:
        decrypted = get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        return json.loads(decrypted or "{}")
    except InvalidToken:
        # Backward compatibility with signed payloads already created locally.
        try:
            loaded = signing.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    except Exception:
        try:
            return json.loads(decrypted or "{}")
        except Exception:
            return {}


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return "Not configured"
    value = str(value)
    if len(value) <= visible * 2:
        return "•" * max(len(value), 8)
    return f"{value[:visible]}{'•' * 8}{value[-visible:]}"
