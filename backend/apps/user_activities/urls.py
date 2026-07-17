# backend/apps/user_activities/urls.py

from django.urls import path

from .views import (
    UserActivitiesDashboardView,
    UserActivitiesListView,
)

app_name = "user_activities"

urlpatterns = [
    path(
        "",
        UserActivitiesListView.as_view(),
        name="list",
    ),

    path(
        "dashboard/",
        UserActivitiesDashboardView.as_view(),
        name="dashboard",
    ),
]

