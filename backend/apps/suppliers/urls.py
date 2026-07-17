from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    SupplierDashboardView,
    SupplierCreateView,
    SupplierDetailView,
    SupplierDocumentCreateView,
    SupplierDocumentViewSet,
    SupplierListView,
    SupplierOfferCreateView,
    SupplierOfferListView,
    SupplierOfferUpdateView,
    SupplierOfferViewSet,
    SupplierPurchaseCreateView,
    SupplierPurchaseDetailView,
    SupplierPurchaseListView,
    SupplierPurchaseUpdateView,
    SupplierPurchaseViewSet,
    SupplierReportsView,
    SupplierUpdateView,
    SupplierViewSet,
    supplier_delete_view,
    supplier_document_delete_view,
    supplier_offer_delete_view,
    supplier_offer_toggle_status_view,
    supplier_purchase_cancel_view,
    supplier_reports_pdf_view,
    supplier_reports_xlsx_view,
    supplier_toggle_status_view,
)

app_name = "suppliers"

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="suppliers_api")
router.register(r"products", SupplierOfferViewSet, basename="supplier_products_api")
router.register(r"purchases", SupplierPurchaseViewSet, basename="supplier_purchases_api")
router.register(r"documents", SupplierDocumentViewSet, basename="supplier_documents_api")

urlpatterns = [
    path("", SupplierDashboardView.as_view(), name="dashboard"),
    path("list/", SupplierListView.as_view(), name="supplier_list"),
    path("create/", SupplierCreateView.as_view(), name="supplier_create"),
    path("<int:id_supplier>/", SupplierDetailView.as_view(), name="supplier_detail"),
    path("<int:id_supplier>/edit/", SupplierUpdateView.as_view(), name="supplier_update"),
    path("<int:id_supplier>/toggle-status/", supplier_toggle_status_view, name="supplier_toggle_status"),
    path("<int:id_supplier>/delete/", supplier_delete_view, name="supplier_delete"),

    path("<int:id_supplier>/products/create/", SupplierOfferCreateView.as_view(), name="offer_create_for_supplier"),
    path("offers/", SupplierOfferListView.as_view(), name="offer_list"),
    path("offers/create/", SupplierOfferCreateView.as_view(), name="offer_create"),
    path("offers/<int:id_supplier_offer>/edit/", SupplierOfferUpdateView.as_view(), name="offer_update"),
    path("offers/<int:id_supplier_offer>/toggle-status/", supplier_offer_toggle_status_view, name="offer_toggle_status"),
    path("offers/<int:id_supplier_offer>/delete/", supplier_offer_delete_view, name="offer_delete"),

    path("<int:id_supplier>/purchases/create/", SupplierPurchaseCreateView.as_view(), name="purchase_create_for_supplier"),
    path("purchases/", SupplierPurchaseListView.as_view(), name="purchase_list"),
    path("purchases/create/", SupplierPurchaseCreateView.as_view(), name="purchase_create"),
    path("purchases/<int:id_supplier_purchase>/", SupplierPurchaseDetailView.as_view(), name="purchase_detail"),
    path("purchases/<int:id_supplier_purchase>/edit/", SupplierPurchaseUpdateView.as_view(), name="purchase_update"),
    path("purchases/<int:id_supplier_purchase>/cancel/", supplier_purchase_cancel_view, name="purchase_cancel"),

    path("<int:id_supplier>/documents/create/", SupplierDocumentCreateView.as_view(), name="document_create_for_supplier"),
    path("purchases/<int:id_supplier_purchase>/documents/create/", SupplierDocumentCreateView.as_view(), name="document_create_for_purchase"),
    path("documents/create/", SupplierDocumentCreateView.as_view(), name="document_create"),
    path("documents/<int:id_supplier_document>/delete/", supplier_document_delete_view, name="document_delete"),

    path("reports/", SupplierReportsView.as_view(), name="reports"),
    path("reports/export/xlsx/", supplier_reports_xlsx_view, name="reports_export_xlsx"),
    path("reports/export/pdf/", supplier_reports_pdf_view, name="reports_export_pdf"),
    path("api/", include(router.urls)),
]
