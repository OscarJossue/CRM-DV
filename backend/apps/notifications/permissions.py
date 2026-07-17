from apps.core.permissions import HasModulePermission


class NotificationPermission(HasModulePermission):
    pass


def user_can_access_notification(user, notification):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return notification.id_user_id == user.id_user
