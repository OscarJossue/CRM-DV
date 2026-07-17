from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CalendarEventCreateView,
    CalendarEventDetailView,
    CalendarEventListView,
    CalendarEventUpdateView,
    CalendarEventViewSet,
    calendar_event_cancel_view,
    calendar_event_complete_view,
)

app_name = "calendar_events"

router = DefaultRouter()
router.register(
    r"calendar-events",
    CalendarEventViewSet,
    basename="calendar_events_api",
)

urlpatterns = [
    path("", CalendarEventListView.as_view(), name="calendar_event_list"),
    path("create/", CalendarEventCreateView.as_view(), name="calendar_event_create"),
    path(
        "projects/<int:id_project>/create/",
        CalendarEventCreateView.as_view(),
        name="calendar_event_create_for_project",
    ),
    path(
        "<int:id_event>/",
        CalendarEventDetailView.as_view(),
        name="calendar_event_detail",
    ),
    path(
        "<int:id_event>/edit/",
        CalendarEventUpdateView.as_view(),
        name="calendar_event_update",
    ),
    path(
        "<int:id_event>/complete/",
        calendar_event_complete_view,
        name="calendar_event_complete",
    ),
    path(
        "<int:id_event>/cancel/",
        calendar_event_cancel_view,
        name="calendar_event_cancel",
    ),
    path("api/", include(router.urls)),
]
