from django.urls import path

from .views import (
    PlatformDocumentCreateView,
    PlatformDocumentDetailView,
    PlatformDocumentExportCSVView,
    PlatformDocumentListView,
    PlatformDocumentPrintView,
    PlatformDocumentUpdateView,
    platform_document_generate_invoice_view,
    PlatformDocumentSendEmailView,
)

app_name = "platform_documents"

urlpatterns = [
    path("", PlatformDocumentListView.as_view(), name="list"),
    path("create/", PlatformDocumentCreateView.as_view(), name="create"),
    path("export.csv", PlatformDocumentExportCSVView.as_view(), name="export_csv"),
    path("<int:id_document>/", PlatformDocumentDetailView.as_view(), name="detail"),
    path("<int:id_document>/edit/", PlatformDocumentUpdateView.as_view(), name="update"),
    path("<int:id_document>/print/", PlatformDocumentPrintView.as_view(), name="print"),
    path("<int:id_document>/generate-invoice/", platform_document_generate_invoice_view, name="generate_invoice"),
    path("<int:id_document>/send-email/", PlatformDocumentSendEmailView.as_view(), name="send_email"),
]