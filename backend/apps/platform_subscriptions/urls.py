from django.urls import path

from .views import (
    PlatformSubscriptionCreateView,
    PlatformSubscriptionDetailView,
    PlatformSubscriptionListView,
    PlatformSubscriptionUpdateView,
    platform_subscription_activate_view,
    platform_subscription_cancel_view,
    platform_subscription_suspend_view,
)

app_name = "platform_subscriptions"

urlpatterns = [
    path("", PlatformSubscriptionListView.as_view(), name="list"),
    path("create/", PlatformSubscriptionCreateView.as_view(), name="create"),
    path("<int:id_subscription>/", PlatformSubscriptionDetailView.as_view(), name="detail"),
    path("<int:id_subscription>/edit/", PlatformSubscriptionUpdateView.as_view(), name="update"),
    path("<int:id_subscription>/activate/", platform_subscription_activate_view, name="activate"),
    path("<int:id_subscription>/suspend/", platform_subscription_suspend_view, name="suspend"),
    path("<int:id_subscription>/cancel/", platform_subscription_cancel_view, name="cancel"),
]
