from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InspectionAssignmentCreateView,
    InspectionAssignmentDetailView,
    InspectionAssignmentListView,
    InspectionAssignmentUpdateView,
    InspectionViewSet,
    assignment_delete_view,
    inspection_assignment_approve_view,
    inspection_assignment_cancel_view,
    inspection_assignment_close_view,
    inspection_assignment_contractor_update_view,
    inspection_assignment_request_corrections_view,
    inspection_assignment_status_update_view,
    inspection_assignment_submit_review_view,
)

app_name = "inspections"

router = DefaultRouter()
router.register(r"inspections", InspectionViewSet, basename="inspections_api")

urlpatterns = [
    path("", InspectionAssignmentListView.as_view(), name="inspection_list"),
    path("create/", InspectionAssignmentCreateView.as_view(), name="inspection_create"),
    path("<int:id_assignment>/", InspectionAssignmentDetailView.as_view(), name="inspection_detail"),
    path(
        "<int:id_assignment>/status/",
        inspection_assignment_status_update_view,
        name="inspection_status_update",
    ),
    path(
        "<int:id_assignment>/field-notes/",
        inspection_assignment_contractor_update_view,
        name="inspection_contractor_update",
    ),
    path(
        "<int:id_assignment>/submit-review/",
        inspection_assignment_submit_review_view,
        name="inspection_submit_review",
    ),
    path(
        "<int:id_assignment>/submit-audit/",
        inspection_assignment_submit_review_view,
        name="inspection_submit_audit",
    ),
    path(
        "<int:id_assignment>/approve/",
        inspection_assignment_approve_view,
        name="inspection_approve",
    ),
    path(
        "<int:id_assignment>/request-corrections/",
        inspection_assignment_request_corrections_view,
        name="inspection_request_corrections",
    ),
    path(
        "<int:id_assignment>/cancel/",
        inspection_assignment_cancel_view,
        name="inspection_cancel",
    ),
    path(
        "<int:id_assignment>/close/",
        inspection_assignment_close_view,
        name="inspection_close",
    ),
    path(
        "<int:id_assignment>/edit/",
        InspectionAssignmentUpdateView.as_view(),
        name="inspection_update",
    ),
    path("<int:id_assignment>/delete/", assignment_delete_view, name="inspection_delete"),
    path("api/", include(router.urls)),
]
