from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ProjectAssignmentCreateView,
    ProjectAssignmentUpdateView,
    ProjectCreateView,
    ProjectDeleteView,
    ProjectDetailView,
    ProjectListView,
    ProjectUpdateView,
    ProjectViewSet,
    project_approve_view,
    project_cancel_view,
    project_close_view,
    project_contractor_update_view,
    project_note_create_view,
    project_pdf_view,
    project_request_corrections_view,
    project_status_update_view,
    project_submit_for_review_view,
)

app_name = "projects"

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="projects_api")

urlpatterns = [
    path("", ProjectListView.as_view(), name="project_list"),
    path("create/", ProjectCreateView.as_view(), name="project_create"),
    path(
        "inspections/<int:id_assignment>/create/",
        ProjectCreateView.as_view(),
        name="project_create_from_inspection",
    ),
    path("<int:id_project>/", ProjectDetailView.as_view(), name="project_detail"),
    path("<int:id_project>/edit/", ProjectUpdateView.as_view(), name="project_update"),
    path("<int:id_project>/delete/", ProjectDeleteView.as_view(), name="project_delete"),
    path(
        "<int:id_project>/assignments/create/",
        ProjectAssignmentCreateView.as_view(),
        name="project_assignment_create",
    ),
    path(
        "assignments/<int:id_assignment>/edit/",
        ProjectAssignmentUpdateView.as_view(),
        name="project_assignment_update",
    ),
    path("<int:id_project>/status/", project_status_update_view, name="project_status_update"),
    path(
        "<int:id_project>/field-notes/",
        project_contractor_update_view,
        name="project_contractor_update",
    ),
    path(
        "<int:id_project>/submit-review/",
        project_submit_for_review_view,
        name="project_submit_review",
    ),
    path(
        "<int:id_project>/submit-audit/",
        project_submit_for_review_view,
        name="project_submit_audit",
    ),
    path("<int:id_project>/approve/", project_approve_view, name="project_approve"),
    path(
        "<int:id_project>/request-corrections/",
        project_request_corrections_view,
        name="project_request_corrections",
    ),
    path("<int:id_project>/cancel/", project_cancel_view, name="project_cancel"),
    path("<int:id_project>/close/", project_close_view, name="project_close"),
    path("<int:id_project>/pdf/", project_pdf_view, name="project_pdf"),
    path(
        "<int:id_project>/notes/create/",
        project_note_create_view,
        name="project_note_create",
    ),
    path("api/", include(router.urls)),
]
