from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    SupervisionCreateView,
    SupervisionDetailView,
    SupervisionListView,
    SupervisionUpdateView,
    SupervisionViewSet,
    supervision_approve_view,
    supervision_final_audit_view,
    supervision_reject_view,
)

app_name = "supervision"

router = DefaultRouter()
router.register(r"supervisions", SupervisionViewSet, basename="supervisions_api")

urlpatterns = [
    path("", SupervisionListView.as_view(), name="supervision_list"),
    path("create/", SupervisionCreateView.as_view(), name="supervision_create"),
    path(
        "projects/<int:id_project>/create/",
        SupervisionCreateView.as_view(),
        name="supervision_create_for_project",
    ),
    path(
        "inspections/<int:id_assignment>/create/",
        SupervisionCreateView.as_view(),
        name="supervision_create_for_inspection",
    ),
    path(
        "<int:id_supervision>/",
        SupervisionDetailView.as_view(),
        name="supervision_detail",
    ),
    path(
        "<int:id_supervision>/edit/",
        SupervisionUpdateView.as_view(),
        name="supervision_update",
    ),
    path(
        "<int:id_supervision>/approve/",
        supervision_approve_view,
        name="supervision_approve",
    ),
    path(
        "<int:id_supervision>/reject/",
        supervision_reject_view,
        name="supervision_reject",
    ),
    path(
        "<int:id_supervision>/final-audit/",
        supervision_final_audit_view,
        name="supervision_final_audit",
    ),
    path("api/", include(router.urls)),
]
