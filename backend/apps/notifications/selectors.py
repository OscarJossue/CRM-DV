from .models import Notification


def notification_list_for_user(user):
    queryset = Notification.objects.select_related(
        "id_user",
        "id_user__id_company",
        "id_user__id_role",
    ).all().order_by("-created_at")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_user=user)


def notification_get_for_user(user, id_notification):
    return notification_list_for_user(user).filter(
        id_notification=id_notification
    ).first()


def unread_notification_count_for_user(user):
    return notification_list_for_user(user).filter(status="unread").count()
