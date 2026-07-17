from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InvoiceCreateView,
    InvoiceDetailView,
    InvoiceListView,
    InvoiceSendView,
    InvoiceUpdateView,
    InvoiceViewSet,
    invoice_generate_view,
    invoice_mark_sent_view,
    invoice_pdf_view,
    invoice_pdf_style_view,
    invoice_void_view,
)

app_name = "invoices"

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoices_api")

urlpatterns = [
    path("", InvoiceListView.as_view(), name="invoice_list"),
    path("create/", InvoiceCreateView.as_view(), name="invoice_create"),
    path(
        "projects/<int:id_project>/create/",
        InvoiceCreateView.as_view(),
        name="invoice_create_for_project",
    ),
    path("<int:id_invoice>/", InvoiceDetailView.as_view(), name="invoice_detail"),
    path(
        "<int:id_invoice>/edit/",
        InvoiceUpdateView.as_view(),
        name="invoice_update",
    ),
    path(
        "<int:id_invoice>/generate/",
        invoice_generate_view,
        name="invoice_generate",
    ),
    path(
        "<int:id_invoice>/send/",
        InvoiceSendView.as_view(),
        name="invoice_send",
    ),
    path(
        "<int:id_invoice>/mark-sent/",
        invoice_mark_sent_view,
        name="invoice_mark_sent",
    ),
    path(
        "<int:id_invoice>/void/",
        invoice_void_view,
        name="invoice_void",
    ),
    path(
        "<int:id_invoice>/pdf-style/",
        invoice_pdf_style_view,
        name="invoice_pdf_style",
    ),
    path(
        "<int:id_invoice>/pdf/",
        invoice_pdf_view,
        name="invoice_pdf",
    ),
    path("api/", include(router.urls)),
]
