from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LeadCreateView,
    LeadDetailView,
    LeadListView,
    LeadUpdateView,
    LeadViewSet,
    lead_convert_view,
)

app_name = "leads"

router = DefaultRouter()
router.register(r"leads", LeadViewSet, basename="leads_api")

urlpatterns = [
    path("", LeadListView.as_view(), name="lead_list"),
    path("create/", LeadCreateView.as_view(), name="lead_create"),
    path("<int:id_lead>/", LeadDetailView.as_view(), name="lead_detail"),
    path("<int:id_lead>/edit/", LeadUpdateView.as_view(), name="lead_update"),
    path("<int:id_lead>/convert/", lead_convert_view, name="lead_convert"),
    path("api/", include(router.urls)),
]
