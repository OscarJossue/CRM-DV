from .models import CalendarEvent


CALENDAR_EVENT_SELECT_RELATED = (
    "id_company",
    "id_project",
    "id_project__id_client",
    "id_inspection_assignment",
    "id_inspection_assignment__client",
    "id_inspection_assignment__inspector",
    "id_estimate",
    "id_estimate__id_client",
    "id_invoice",
    "id_invoice__id_client",
    "id_payment",
    "id_payment__id_client",
    "id_client",
    "id_opportunity",
    "id_opportunity__id_client",
    "id_assigned_user",
)


def calendar_event_list_for_user(user):
    queryset = CalendarEvent.objects.select_related(
        *CALENDAR_EVENT_SELECT_RELATED
    ).all().order_by(
        "event_date",
        "start_time",
        "title",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def calendar_event_get_for_user(user, id_event):
    return calendar_event_list_for_user(user).filter(
        id_event=id_event,
    ).first()


def list_calendar_events(company=None):
    queryset = CalendarEvent.objects.select_related(
        *CALENDAR_EVENT_SELECT_RELATED
    ).all().order_by(
        "event_date",
        "start_time",
        "title",
    )

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_calendar_events_by_id(pk):
    return CalendarEvent.objects.filter(pk=pk).first()
