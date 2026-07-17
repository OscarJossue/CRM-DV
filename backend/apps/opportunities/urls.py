from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LeadCreateView,
    LeadDetailView,
    LeadListView,
    LeadUpdateView,
    LeadViewSet,
    lead_convert_view,
    lead_delete_view,
    lead_status_update_view,
)

app_name = "opportunities"

router = DefaultRouter()
router.register(r"opportunities", LeadViewSet, basename="opportunities_api")

urlpatterns = [
    path("", LeadListView.as_view(), name="opportunity_list"),
    path("create/", LeadCreateView.as_view(), name="opportunity_create"),
    path("<int:id_lead>/", LeadDetailView.as_view(), name="opportunity_detail"),
    path("<int:id_lead>/edit/", LeadUpdateView.as_view(), name="opportunity_update"),
    path("<int:id_lead>/status/", lead_status_update_view, name="opportunity_status_update"),
    path("<int:id_lead>/convert/", lead_convert_view, name="opportunity_convert"),
    path("<int:id_lead>/delete/", lead_delete_view, name="opportunity_delete"),
    path("api/", include(router.urls)),
]