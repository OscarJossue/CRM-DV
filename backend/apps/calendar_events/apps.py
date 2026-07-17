from django.apps import AppConfig


class CalendarEventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.calendar_events"
    label = "calendar_events"
    verbose_name = "Calendar Events"
