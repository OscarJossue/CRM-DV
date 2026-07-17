from django.urls import path

from .views import (
    PlatformCalendarEventCreateView,
    PlatformCalendarEventDetailView,
    PlatformCalendarEventUpdateView,
    PlatformCalendarView,
    platform_calendar_event_cancel_view,
    platform_calendar_event_done_view,
)

app_name = "platform_calendar"

urlpatterns = [
    path("", PlatformCalendarView.as_view(), name="list"),
    path("create/", PlatformCalendarEventCreateView.as_view(), name="create"),
    path("<int:id_event>/", PlatformCalendarEventDetailView.as_view(), name="detail"),
    path("<int:id_event>/edit/", PlatformCalendarEventUpdateView.as_view(), name="update"),
    path("<int:id_event>/done/", platform_calendar_event_done_view, name="done"),
    path("<int:id_event>/cancel/", platform_calendar_event_cancel_view, name="cancel"),
]