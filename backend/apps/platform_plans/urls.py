from django.urls import path

from .views import (
    PlatformPlanCreateView,
    PlatformPlanDetailView,
    PlatformPlanListView,
    PlatformPlanUpdateView,
    platform_plan_activate_view,
    platform_plan_deactivate_view,
)

app_name = "platform_plans"

urlpatterns = [
    path("", PlatformPlanListView.as_view(), name="list"),
    path("create/", PlatformPlanCreateView.as_view(), name="create"),
    path("<int:id_plan>/", PlatformPlanDetailView.as_view(), name="detail"),
    path("<int:id_plan>/edit/", PlatformPlanUpdateView.as_view(), name="update"),
    path("<int:id_plan>/activate/", platform_plan_activate_view, name="activate"),
    path("<int:id_plan>/deactivate/", platform_plan_deactivate_view, name="deactivate"),
]