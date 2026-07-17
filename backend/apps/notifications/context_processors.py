from .models import Notification
from .models.choices import NOTIFICATION_STATUS_ARCHIVED, NOTIFICATION_STATUS_UNREAD
from apps.user_activities.selectors import get_user_activities_dashboard


def _company_base_path(company):
    return f"/{str(company.slug).strip('/')}/"


def _normalize_detail_url(url, company):
    base_path = _company_base_path(company)

    if not url or url == "#":
        return f"{base_path}notifications/"

    if str(url).startswith("http://") or str(url).startswith("https://"):
        return url

    if str(url).startswith("/"):
        return url

    return f"{base_path}{str(url).lstrip('/')}"


def notification_bell_context(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {}

    if user.is_superuser or user.is_staff:
        return {}

    company = getattr(user, "id_company", None)

    if not company or not getattr(company, "slug", None):
        return {}

    base_path = _company_base_path(company)

    notifications_queryset = (
        Notification.objects.filter(id_user=user)
        .exclude(status=NOTIFICATION_STATUS_ARCHIVED)
        .order_by("-created_at")
    )

    unread_count = notifications_queryset.filter(
        status=NOTIFICATION_STATUS_UNREAD
    ).count()

    floating_notifications = list(notifications_queryset[:3])

    for notification in floating_notifications:
        notification.url = f"{base_path}notifications/{notification.id_notification}/"
        notification.detail_url = notification.url

    pending_activity_count = 0

    try:
        dashboard_data = get_user_activities_dashboard(
            user=user,
            company_slug=company.slug,
        )

        pending_items = dashboard_data.get("pending", [])[:8]
        pending_activity_count = len(pending_items)

        for item in pending_items:
            detail_url = _normalize_detail_url(
                item.get("detail_url") or item.get("url") or "#",
                company,
            )

            floating_notifications.append({
                "title": f"{item.get('type', 'Activity')} {item.get('code', '')}".strip(),
                "message": f"{item.get('title', 'Pending activity')} requires attention.",
                "url": detail_url,
                "detail_url": detail_url,
                "status": item.get("status", ""),
                "created_at": item.get("created_at"),
            })

    except Exception:
        pending_activity_count = 0

    return {
        "floating_notifications": floating_notifications[:8],
        "floating_unread_notifications_count": unread_count + pending_activity_count,
        "floating_notifications_page_url": f"{base_path}notifications/",
    }