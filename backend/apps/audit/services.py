from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import SystemLog
from .models.choices import (
    ACTION_SYSTEM,
    CRITICAL_ACTION_TYPES,
    RESULT_SUCCESS,
    SECURITY_ACTION_TYPES,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_SECURITY,
)


def get_client_ip(request):
    if not request:
        return None

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    candidate = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")

    if candidate in {"", "unknown"}:
        return None
    return candidate


def _actor_snapshot(user):
    if not user or not getattr(user, "is_authenticated", False):
        return "", ""

    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = (get_full_name() or "").strip()

    if not full_name:
        full_name = " ".join(
            part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part
        ).strip()

    return full_name, (getattr(user, "email", "") or "").strip()


def _retention_days(action_type, severity):
    if severity in {SEVERITY_CRITICAL, SEVERITY_SECURITY} or action_type in (
        CRITICAL_ACTION_TYPES | SECURITY_ACTION_TYPES
    ):
        return int(getattr(settings, "AUDIT_CRITICAL_RETENTION_DAYS", 7))
    return int(getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 3))


def _default_severity(action_type):
    if action_type in SECURITY_ACTION_TYPES:
        return SEVERITY_SECURITY
    if action_type in CRITICAL_ACTION_TYPES:
        return SEVERITY_CRITICAL
    return SEVERITY_INFO


@transaction.atomic
def log_system_action(
    *,
    user=None,
    company=None,
    module=None,
    action=None,
    action_type=ACTION_SYSTEM,
    request=None,
    object_type="",
    object_id="",
    object_label="",
    changes=None,
    severity=None,
    result=RESULT_SUCCESS,
    expires_at=None,
):
    if not company and user and getattr(user, "id_company_id", None):
        company = user.id_company

    if not company and request:
        company = getattr(request, "current_company", None)

    if not company:
        return None

    actor_name, actor_email = _actor_snapshot(user)
    severity = severity or _default_severity(action_type)
    if expires_at is None:
        expires_at = timezone.now() + timedelta(days=_retention_days(action_type, severity))

    user_agent = ""
    request_id = None
    if request:
        user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
        request_id = getattr(request, "audit_request_id", None)

    return SystemLog.objects.create(
        id_company=company,
        id_user=user if user and getattr(user, "is_authenticated", False) else None,
        actor_name=actor_name,
        actor_email=actor_email,
        module=(module or "general")[:100],
        action=(action or "")[:500] or None,
        action_type=action_type,
        object_type=(object_type or "")[:120],
        object_id=str(object_id or "")[:100],
        object_label=(object_label or "")[:255],
        changes=changes or {},
        severity=severity,
        result=result,
        ip=get_client_ip(request),
        user_agent=user_agent,
        request_id=request_id,
        expires_at=expires_at,
    )


def purge_expired_system_logs(*, now=None, batch_size=5000):
    """Delete expired audit records in small batches to avoid long DB locks."""

    now = now or timezone.now()
    batch_size = max(100, min(int(batch_size), 20000))
    standard_cutoff = now - timedelta(days=int(getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 3)))
    critical_cutoff = now - timedelta(days=int(getattr(settings, "AUDIT_CRITICAL_RETENTION_DAYS", 7)))
    deleted_total = 0

    critical_record = Q(severity__in=[SEVERITY_CRITICAL, SEVERITY_SECURITY]) | Q(
        action_type__in=CRITICAL_ACTION_TYPES | SECURITY_ACTION_TYPES
    )
    expired_filter = (
        Q(expires_at__lte=now)
        | (critical_record & Q(created_at__lt=critical_cutoff))
        | (~critical_record & Q(created_at__lt=standard_cutoff))
    )

    while True:
        ids = list(
            SystemLog.objects.filter(expired_filter)
            .order_by("expires_at", "created_at")
            .values_list("id_log", flat=True)[:batch_size]
        )
        if not ids:
            break
        deleted, _ = SystemLog.objects.filter(id_log__in=ids).delete()
        deleted_total += deleted

    return deleted_total


def create_audit(**data):
    return log_system_action(**data)


def update_audit(instance, **data):
    raise ValueError("Audit records are immutable and cannot be updated.")
