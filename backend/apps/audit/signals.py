from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import PurePath
from uuid import UUID

from django.db import models
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .context import get_current_request
from .models.choices import (
    ACTION_APPROVED,
    ACTION_CANCELLED,
    ACTION_CREATED,
    ACTION_DELETED,
    ACTION_FILE_UPLOADED,
    ACTION_PAYMENT_REGISTERED,
    ACTION_PERMISSIONS_UPDATED,
    ACTION_REJECTED,
    ACTION_SENT,
    ACTION_STATUS_CHANGED,
    ACTION_UPDATED,
    ACTION_VOIDED,
    SEVERITY_CRITICAL,
)
from .services import log_system_action


TRACKED_APPS = {
    "accounts",
    "calendar_events",
    "clients",
    "companies",
    "company_modules",
    "contracts",
    "employees",
    "estimates",
    "evidence",
    "inspections",
    "integrations",
    "invoices",
    "leads",
    "notifications",
    "opportunities",
    "payments",
    "projects",
    "smtp_settings",
    "supervision",
    "suppliers",
}

EXCLUDED_MODELS = {
    # Child rows and machine-generated snapshots would create duplicate/noisy history.
    ("estimates", "estimateitem"),
    ("invoices", "invoiceitem"),
    ("payments", "paymentallocation"),
    ("payments", "clientcreditaccount"),
    ("payments", "clientcreditmovement"),
    ("payments", "financialmovement"),
    ("suppliers", "supplierpurchaseitem"),
    ("integrations", "integrationlog"),
    ("integrations", "googlecalendareventlink"),
    ("integrations", "googledriveupload"),
    ("integrations", "googlesheetexport"),
    ("integrations", "googleanalyticssnapshot"),
    ("integrations", "googleadssnapshot"),
    ("notifications", "notification"),
}

IGNORED_FIELD_NAMES = {
    "created_at",
    "updated_at",
    "modified_at",
    "last_login",
    "last_seen",
    "password",
}

SENSITIVE_FRAGMENTS = {
    "password",
    "secret",
    "token",
    "credential",
    "api_key",
    "private_key",
    "signature",
}

MODULE_LABELS = {
    "accounts": "users",
    "calendar_events": "calendar",
    "clients": "clients",
    "companies": "companies",
    "company_modules": "company_modules",
    "contracts": "contracts",
    "employees": "employees",
    "estimates": "estimates",
    "evidence": "evidence",
    "inspections": "inspections",
    "integrations": "integrations",
    "invoices": "invoices",
    "leads": "leads",
    "opportunities": "opportunities",
    "payments": "payments",
    "projects": "projects",
    "smtp_settings": "smtp_settings",
    "supervision": "supervision",
    "suppliers": "suppliers",
}

LABEL_FIELD_PRIORITY = (
    "invoice_number",
    "estimate_number",
    "contract_number",
    "payment_number",
    "project_code",
    "client_code",
    "opportunity_code",
    "inspection_code",
    "purchase_number",
    "offer_number",
    "document_number",
    "name",
    "title",
    "project_name",
    "company_name",
    "email",
)


def _is_tracked(sender):
    meta = getattr(sender, "_meta", None)
    if not meta or meta.abstract:
        return False
    key = (meta.app_label, meta.model_name)
    return meta.app_label in TRACKED_APPS and key not in EXCLUDED_MODELS and meta.app_label != "audit"


def _safe_value(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, PurePath):
        return str(value)
    if hasattr(value, "name") and not isinstance(value, str):
        value = getattr(value, "name", "")
    text = str(value)
    return text if len(text) <= 240 else f"{text[:237]}..."


def _field_value(instance, field):
    try:
        if isinstance(field, models.ForeignKey):
            return getattr(instance, field.attname, None)
        return field.value_from_object(instance)
    except Exception:
        return None


def _snapshot(instance):
    values = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        lowered = name.lower()
        if name in IGNORED_FIELD_NAMES:
            continue
        if any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS):
            continue
        values[name] = _safe_value(_field_value(instance, field))
    return values


def _changes(old_values, new_values):
    result = {}
    for key in sorted(set(old_values) | set(new_values)):
        old = old_values.get(key)
        new = new_values.get(key)
        if old != new:
            result[key] = {"old": old, "new": new}
    return result


def _related_company(instance, depth=0, visited=None):
    if instance is None or depth > 2:
        return None

    visited = visited or set()
    identity = (instance.__class__, getattr(instance, "pk", None), id(instance))
    if identity in visited:
        return None
    visited.add(identity)

    meta = getattr(instance, "_meta", None)
    if not meta:
        return None

    if meta.app_label == "companies" and meta.model_name == "company":
        return instance

    for attr in ("id_company", "company"):
        try:
            company = getattr(instance, attr, None)
        except Exception:
            company = None
        if company is not None and getattr(getattr(company, "_meta", None), "model_name", "") == "company":
            return company

    for field in meta.concrete_fields:
        if not isinstance(field, models.ForeignKey):
            continue
        related_model = field.remote_field.model
        related_meta = getattr(related_model, "_meta", None)
        if not related_meta or related_meta.app_label == "audit":
            continue
        try:
            related = getattr(instance, field.name, None)
        except Exception:
            related = None
        company = _related_company(related, depth + 1, visited)
        if company is not None:
            return company

    return None


def _object_label(instance):
    for field_name in LABEL_FIELD_PRIORITY:
        value = getattr(instance, field_name, None)
        if value:
            return str(value)[:255]
    try:
        value = str(instance)
    except Exception:
        value = ""
    if value and " object (" not in value:
        return value[:255]
    return f"{instance._meta.verbose_name.title()} #{getattr(instance, 'pk', '')}"[:255]


def _infer_action(instance, created, changes):
    model_name = instance._meta.model_name

    if model_name in {"rolepermission", "companymodule"}:
        return ACTION_PERMISSIONS_UPDATED

    file_changed = False
    for field in instance._meta.concrete_fields:
        if isinstance(field, (models.FileField, models.ImageField)) and field.name in changes:
            changed_value = changes[field.name]
            new_value = changed_value.get("new") if isinstance(changed_value, dict) else changed_value
            if new_value:
                file_changed = True
                break

    if created:
        if model_name == "payment":
            return ACTION_PAYMENT_REGISTERED
        if file_changed:
            return ACTION_FILE_UPLOADED
        return ACTION_CREATED

    if file_changed:
        return ACTION_FILE_UPLOADED

    status_change = next(
        (changes.get(name) for name in ("status", "payment_status", "invoice_status", "approval_status") if changes.get(name)),
        None,
    )
    if status_change:
        next_status = str(status_change.get("new") or "").strip().lower()
        if next_status in {"void", "voided", "annulled", "anulado"}:
            return ACTION_VOIDED
        if next_status in {"cancelled", "canceled", "cancelado"}:
            return ACTION_CANCELLED
        if next_status in {"approved", "aprobado"}:
            return ACTION_APPROVED
        if next_status in {"rejected", "rechazado"}:
            return ACTION_REJECTED
        if next_status in {"sent", "enviado"}:
            return ACTION_SENT
        return ACTION_STATUS_CHANGED

    return ACTION_UPDATED


def _request_actor_and_company(instance):
    request = get_current_request()
    user = getattr(request, "user", None) if request else None
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    company = getattr(request, "current_company", None) if request else None
    company = company or _related_company(instance)
    return request, user, company


def _write_log(instance, *, action_type, changes=None, severity=None):
    request, user, company = _request_actor_and_company(instance)
    if company is None:
        return

    model_label = instance._meta.verbose_name.title()
    object_id = getattr(instance, "pk", "")
    action = f"{instance._meta.label_lower}:{action_type}"
    if changes:
        action = f"{action}:{','.join(sorted(changes))}"[:500]

    try:
        log_system_action(
            user=user,
            company=company,
            module=MODULE_LABELS.get(instance._meta.app_label, instance._meta.app_label),
            action=action,
            action_type=action_type,
            request=request,
            object_type=model_label,
            object_id=object_id,
            object_label=_object_label(instance),
            changes=changes or {},
            severity=severity,
        )
    except Exception:
        # Audit logging must never block the business operation.
        return


@receiver(pre_save, dispatch_uid="audit_capture_previous_state")
def capture_previous_state(sender, instance, raw=False, **kwargs):
    if raw or not _is_tracked(sender):
        return
    if not getattr(instance, "pk", None):
        instance._audit_previous_values = {}
        return
    try:
        previous = sender._default_manager.filter(pk=instance.pk).first()
    except Exception:
        previous = None
    instance._audit_previous_values = _snapshot(previous) if previous is not None else {}


@receiver(post_save, dispatch_uid="audit_log_model_save")
def log_model_save(sender, instance, created=False, raw=False, **kwargs):
    if raw or not _is_tracked(sender):
        return
    previous = getattr(instance, "_audit_previous_values", {})
    current = _snapshot(instance)
    change_set = current if created else _changes(previous, current)
    if not created and not change_set:
        return
    action_type = _infer_action(instance, created, change_set)
    severity = SEVERITY_CRITICAL if action_type == ACTION_PERMISSIONS_UPDATED else None
    _write_log(instance, action_type=action_type, changes=change_set, severity=severity)


@receiver(pre_delete, dispatch_uid="audit_capture_deleted_state")
def capture_deleted_state(sender, instance, origin=None, **kwargs):
    if not _is_tracked(sender):
        return
    origin_model = getattr(origin, "model", None) or getattr(origin, "__class__", None)
    instance._audit_is_delete_origin = origin is None or origin is instance or origin_model is sender
    if not instance._audit_is_delete_origin:
        return
    instance._audit_deleted_company = _related_company(instance)
    instance._audit_deleted_label = _object_label(instance)
    instance._audit_deleted_values = _snapshot(instance)


@receiver(post_delete, dispatch_uid="audit_log_model_delete")
def log_model_delete(sender, instance, origin=None, **kwargs):
    if not _is_tracked(sender) or not getattr(instance, "_audit_is_delete_origin", True):
        return
    request = get_current_request()
    user = getattr(request, "user", None) if request else None
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    company = getattr(instance, "_audit_deleted_company", None)
    if company is None:
        company = getattr(request, "current_company", None) if request else None
    if company is None:
        return
    try:
        log_system_action(
            user=user,
            company=company,
            module=MODULE_LABELS.get(instance._meta.app_label, instance._meta.app_label),
            action=f"{instance._meta.label_lower}:{ACTION_DELETED}",
            action_type=ACTION_DELETED,
            request=request,
            object_type=instance._meta.verbose_name.title(),
            object_id=getattr(instance, "pk", ""),
            object_label=getattr(instance, "_audit_deleted_label", ""),
            changes={"deleted_record": getattr(instance, "_audit_deleted_values", {})},
            severity=SEVERITY_CRITICAL,
        )
    except Exception:
        return
