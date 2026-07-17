from django.conf import settings
from django.db import transaction

from .models import PlatformAuditLog
from .models.choices import PLATFORM_AUDIT_ACTION_OTHER


def get_client_ip(request):
    if not request:
        return None

    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()

    return request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    if not request:
        return None

    return request.META.get("HTTP_USER_AGENT")


@transaction.atomic
def log_platform_action(
    *,
    user=None,
    company=None,
    module_name=None,
    action=PLATFORM_AUDIT_ACTION_OTHER,
    object_id=None,
    object_label=None,
    description=None,
    request=None,
    metadata=None,
):
    if not module_name:
        module_name = "platform"

    actor_user = user if user and getattr(user, "is_authenticated", False) else None

    audit_log = PlatformAuditLog.objects.create(
        actor_user=actor_user,
        id_company=company,
        module_name=module_name,
        action=action or PLATFORM_AUDIT_ACTION_OTHER,
        object_id=str(object_id) if object_id is not None else None,
        object_label=object_label,
        description=description,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        metadata=metadata or {},
    )

    return audit_log