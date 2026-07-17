from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContractCreateView,
    ContractDetailView,
    ContractListView,
    ContractPDFView,
    ContractSendView,
    ContractUpdateView,
    ContractViewSet,
    contract_activate_view,
    contract_cancel_view,
    contract_complete_view,
    contract_generate_view,
    contract_mark_signed_view,
    contract_void_view,
    public_contract_approve_view,
    public_contract_preview_view,
    public_contract_reject_view,
    public_contract_sign_view,
)

app_name = "contracts"

router = DefaultRouter()
router.register(r"contracts", ContractViewSet, basename="contracts_api")

urlpatterns = [
    path("", ContractListView.as_view(), name="contract_list"),
    path("create/", ContractCreateView.as_view(), name="contract_create"),
    path(
        "projects/<int:id_project>/create/",
        ContractCreateView.as_view(),
        name="contract_create_for_project",
    ),
    path("<int:id_contract>/", ContractDetailView.as_view(), name="contract_detail"),
    path(
        "<int:id_contract>/edit/",
        ContractUpdateView.as_view(),
        name="contract_update",
    ),
    path(
        "<int:id_contract>/pdf/",
        ContractPDFView.as_view(),
        name="contract_pdf",
    ),
    path(
        "<int:id_contract>/send/",
        ContractSendView.as_view(),
        name="contract_send",
    ),
    path(
        "<int:id_contract>/generate/",
        contract_generate_view,
        name="contract_generate",
    ),
    path(
        "<int:id_contract>/mark-signed/",
        contract_mark_signed_view,
        name="contract_mark_signed",
    ),
    path(
        "<int:id_contract>/void/",
        contract_void_view,
        name="contract_void",
    ),

    # Legacy compatibility routes
    path(
        "<int:id_contract>/activate/",
        contract_activate_view,
        name="contract_activate",
    ),
    path(
        "<int:id_contract>/complete/",
        contract_complete_view,
        name="contract_complete",
    ),
    path(
        "<int:id_contract>/cancel/",
        contract_cancel_view,
        name="contract_cancel",
    ),
        # Public customer contract flow - no login required
    path(
        "public/<uuid:token>/",
        public_contract_preview_view,
        name="public_contract_preview",
    ),
    path(
        "public/<uuid:token>/approve/",
        public_contract_approve_view,
        name="public_contract_approve",
    ),
    path(
        "public/<uuid:token>/reject/",
        public_contract_reject_view,
        name="public_contract_reject",
    ),
    path(
        "public/<uuid:token>/sign/<uuid:sign_token>/",
        public_contract_sign_view,
        name="public_contract_sign",
    ),
    path("api/", include(router.urls)),
]