from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EstimateCreateView,
    EstimateDetailView,
    EstimateListView,
    EstimateProjectCreateView,
    EstimateSendView,
    EstimateUpdateView,
    EstimateViewSet,
    estimate_approve_view,
    estimate_cancel_view,
    estimate_delete_view,
    estimate_pdf_view,
    estimate_pdf_style_view,
    estimate_project_update_view,
    estimate_projects_for_client_view,
    estimate_reject_view,
    public_estimate_approve_view,
    public_estimate_preview_view,
    public_estimate_reject_view,
)

app_name = "estimates"

router = DefaultRouter()
router.register(r"estimates", EstimateViewSet, basename="estimates_api")

urlpatterns = [
    path("", EstimateListView.as_view(), name="estimate_list"),
    path(
        "client/<int:id_client>/projects/",
        estimate_projects_for_client_view,
        name="estimate_projects_for_client",
    ),
    path(
        "public/<uuid:token>/",
        public_estimate_preview_view,
        name="public_estimate_preview",
    ),
    path(
        "public/<uuid:token>/approve/",
        public_estimate_approve_view,
        name="public_estimate_approve",
    ),
    path(
        "public/<uuid:token>/reject/",
        public_estimate_reject_view,
        name="public_estimate_reject",
    ),
    path("create/", EstimateCreateView.as_view(), name="estimate_create"),
    path(
        "projects/<int:id_project>/create/",
        EstimateCreateView.as_view(),
        name="estimate_create_for_project",
    ),
    path(
        "inspections/<int:id_assignment>/create/",
        EstimateCreateView.as_view(),
        name="estimate_create_from_inspection",
    ),
    path(
        "<int:id_estimate>/send/",
        EstimateSendView.as_view(),
        name="estimate_send",
    ),
    path(
        "<int:id_estimate>/edit/",
        EstimateUpdateView.as_view(),
        name="estimate_update",
    ),
    path(
        "<int:id_estimate>/approve/",
        estimate_approve_view,
        name="estimate_approve",
    ),
    path(
        "<int:id_estimate>/reject/",
        estimate_reject_view,
        name="estimate_reject",
    ),
    path(
        "<int:id_estimate>/cancel/",
        estimate_cancel_view,
        name="estimate_cancel",
    ),
    path(
        "<int:id_estimate>/delete/",
        estimate_delete_view,
        name="estimate_delete",
    ),
    path(
        "<int:id_estimate>/project/create/",
        EstimateProjectCreateView.as_view(),
        name="estimate_project_create",
    ),
    path(
        "<int:id_estimate>/project/update/",
        estimate_project_update_view,
        name="estimate_project_update",
    ),
    path(
        "<int:id_estimate>/pdf-style/",
        estimate_pdf_style_view,
        name="estimate_pdf_style",
    ),
    path(
        "<int:id_estimate>/pdf/",
        estimate_pdf_view,
        name="estimate_pdf",
    ),
    path(
        "<int:id_estimate>/",
        EstimateDetailView.as_view(),
        name="estimate_detail",
    ),
    path("api/", include(router.urls)),
]
