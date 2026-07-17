from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import SystemLog


def system_log_list_for_user(user, company=None):
    queryset = SystemLog.objects.select_related("id_company", "id_user").all()

    if not user or not user.is_authenticated:
        return queryset.none()

    if company is not None:
        return queryset.filter(id_company=company)

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company_id=user.id_company_id)


def apply_system_log_filters(queryset, params):
    search = (params.get("q") or "").strip()
    module = (params.get("module") or "").strip()
    action_type = (params.get("action_type") or "").strip()
    severity = (params.get("severity") or "").strip()
    user_id = (params.get("user") or "").strip()
    date_from = parse_date((params.get("date_from") or "").strip())
    date_to = parse_date((params.get("date_to") or "").strip())

    if search:
        queryset = queryset.filter(
            Q(actor_name__icontains=search)
            | Q(actor_email__icontains=search)
            | Q(id_user__email__icontains=search)
            | Q(module__icontains=search)
            | Q(action__icontains=search)
            | Q(object_type__icontains=search)
            | Q(object_label__icontains=search)
            | Q(object_id__icontains=search)
            | Q(ip__icontains=search)
        )

    if module:
        queryset = queryset.filter(module=module)
    if action_type:
        queryset = queryset.filter(action_type=action_type)
    if severity:
        queryset = queryset.filter(severity=severity)
    if user_id.isdigit():
        queryset = queryset.filter(id_user_id=int(user_id))

    current_timezone = timezone.get_current_timezone()
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), current_timezone)
        queryset = queryset.filter(created_at__gte=start)
    if date_to:
        end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), current_timezone)
        queryset = queryset.filter(created_at__lt=end)

    return queryset.order_by("-created_at", "-id_log")


def system_log_get_for_user(user, id_log, company=None):
    return system_log_list_for_user(user, company=company).filter(id_log=id_log).first()


def system_log_filter_options(queryset):
    modules = list(
        queryset.exclude(module__isnull=True)
        .exclude(module="")
        .values_list("module", flat=True)
        .distinct()
        .order_by("module")
    )
    actors = list(
        queryset.exclude(id_user__isnull=True)
        .values("id_user", "actor_name", "actor_email", "id_user__email")
        .distinct()
        .order_by("actor_name", "actor_email", "id_user__email")
    )
    return {"modules": modules, "actors": actors}


def system_log_summary(queryset):
    today = timezone.localdate()
    return queryset.aggregate(
        total=Count("id_log"),
        today=Count("id_log", filter=Q(created_at__date=today)),
        critical=Count("id_log", filter=Q(severity__in=["critical", "security"])),
        users=Count("id_user", distinct=True, filter=Q(id_user__isnull=False)),
    )


def list_audit(company=None):
    queryset = SystemLog.objects.select_related("id_company", "id_user").all()
    if company:
        queryset = queryset.filter(id_company=company)
    return queryset.order_by("-created_at", "-id_log")


def get_audit_by_id(pk):
    return SystemLog.objects.filter(pk=pk).first()
