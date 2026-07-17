from django.urls import path

from .views import PlatformEmailComposeView, PlatformEmailLogListView

app_name = "platform_email"

urlpatterns = [
    path("", PlatformEmailLogListView.as_view(), name="list"),
    path("compose/", PlatformEmailComposeView.as_view(), name="compose"),

    # Backward-compatible route. The UI should use compose/.
    path("test/", PlatformEmailComposeView.as_view(), name="test"),
]