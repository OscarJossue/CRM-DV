from django.urls import path

from .views import (
    PlatformPaymentCreateView,
    PlatformPaymentDetailView,
    PlatformPaymentExportCSVView,
    PlatformPaymentListView,
    PlatformPaymentUpdateView,
    platform_payment_mark_paid_view,
    platform_payment_void_view,
)

app_name = "platform_payments"

urlpatterns = [
    path("", PlatformPaymentListView.as_view(), name="list"),
    path("create/", PlatformPaymentCreateView.as_view(), name="create"),
    path("export.csv", PlatformPaymentExportCSVView.as_view(), name="export_csv"),
    path("<int:id_payment>/", PlatformPaymentDetailView.as_view(), name="detail"),
    path("<int:id_payment>/edit/", PlatformPaymentUpdateView.as_view(), name="update"),
    path("<int:id_payment>/mark-paid/", platform_payment_mark_paid_view, name="mark_paid"),
    path("<int:id_payment>/void/", platform_payment_void_view, name="void"),
]