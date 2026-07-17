from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (
    NotificationCreateView,
    NotificationDetailView,
    NotificationListView,
    NotificationUpdateView,
    NotificationViewSet,
    notification_archive_view,
    notification_mark_all_read_view,
    notification_mark_read_view,
    notification_mark_unread_view,
)

app_name = "notifications"

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notifications_api")


urlpatterns = [
    path("", NotificationListView.as_view(), name="notification_list"),
    path("create/", NotificationCreateView.as_view(), name="notification_create"),
    path("mark-all-read/", notification_mark_all_read_view, name="notification_mark_all_read"),
    path("<int:id_notification>/", NotificationDetailView.as_view(), name="notification_detail"),
    path("<int:id_notification>/edit/", NotificationUpdateView.as_view(), name="notification_update"),
    path("<int:id_notification>/mark-read/", notification_mark_read_view, name="notification_mark_read"),
    path("<int:id_notification>/mark-unread/", notification_mark_unread_view, name="notification_mark_unread"),
    path("<int:id_notification>/archive/", notification_archive_view, name="notification_archive"),
    path("api/", include(router.urls)),
]