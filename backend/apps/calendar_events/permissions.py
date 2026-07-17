from apps.core.permissions import HasModulePermission


class CalendarEventPermission(HasModulePermission):
    pass


def user_can_access_calendar_event(user, calendar_event):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return calendar_event.id_company_id == user.id_company_id
