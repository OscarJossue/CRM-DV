from django.urls import path

from .views import (
    PlatformNotificationDetailView,
    PlatformNotificationListView,
    send_due_notifications_view,
)

app_name = "platform_notifications"

urlpatterns = [
    path("", PlatformNotificationListView.as_view(), name="list"),
    path("send-due/", send_due_notifications_view, name="send_due"),
    path("<int:id_notification>/", PlatformNotificationDetailView.as_view(), name="detail"),
]