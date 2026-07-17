from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EvidenceFileCreateView,
    EvidenceFileDetailView,
    EvidenceFileListView,
    EvidenceFileUpdateView,
    EvidenceFileViewSet,
)

app_name = "evidence"

router = DefaultRouter()
router.register(r"evidence-files", EvidenceFileViewSet, basename="evidence_files_api")

urlpatterns = [
    path("", EvidenceFileListView.as_view(), name="evidence_file_list"),
    path("create/", EvidenceFileCreateView.as_view(), name="evidence_file_create"),
    path(
        "projects/<int:id_project>/create/",
        EvidenceFileCreateView.as_view(),
        name="evidence_file_create_for_project",
    ),
    path(
        "<int:id_file>/",
        EvidenceFileDetailView.as_view(),
        name="evidence_file_detail",
    ),
    path(
        "<int:id_file>/edit/",
        EvidenceFileUpdateView.as_view(),
        name="evidence_file_update",
    ),
    path("api/", include(router.urls)),
]
