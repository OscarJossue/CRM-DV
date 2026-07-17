from django.urls import path

from .views import (
    PlatformUserCreateView,
    PlatformUserDetailView,
    PlatformUserListView,
    PlatformUserUpdateView,
)

app_name = "platform_users"

urlpatterns = [
    path("", PlatformUserListView.as_view(), name="user_list"),
    path("create/", PlatformUserCreateView.as_view(), name="user_create"),
    path("<int:id_user>/", PlatformUserDetailView.as_view(), name="user_detail"),
    path("<int:id_user>/edit/", PlatformUserUpdateView.as_view(), name="user_update"),
]