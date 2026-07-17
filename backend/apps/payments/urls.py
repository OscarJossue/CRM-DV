from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FinanceClientDetailView,
    FinanceClientListView,
    PaymentCreateView,
    PaymentDetailView,
    PaymentListView,
    PaymentUpdateView,
    PaymentViewSet,
    apply_credit_to_invoice_view,
    payment_cancel_view,
    payment_confirm_view,
    payment_mark_paid_view,
    payment_mark_pending_view,
    payment_reject_view,
    payment_verify_view,
    payment_void_view,
)

app_name = "payments"

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payments_api")

urlpatterns = [
    path("", PaymentListView.as_view(), name="payment_list"),
    path("create/", PaymentCreateView.as_view(), name="payment_create"),
    path(
        "invoices/<int:id_invoice>/create/",
        PaymentCreateView.as_view(),
        name="payment_create_for_invoice",
    ),
    path(
        "invoices/<int:id_invoice>/apply-credit/",
        apply_credit_to_invoice_view,
        name="apply_credit_to_invoice",
    ),
    path(
        "finance/clients/",
        FinanceClientListView.as_view(),
        name="finance_clients",
    ),
    path(
        "finance/clients/<int:id_client>/",
        FinanceClientDetailView.as_view(),
        name="finance_client_detail",
    ),
    path("<int:id_payment>/", PaymentDetailView.as_view(), name="payment_detail"),
    path("<int:id_payment>/edit/", PaymentUpdateView.as_view(), name="payment_update"),
    path(
        "<int:id_payment>/mark-pending/",
        payment_mark_pending_view,
        name="payment_mark_pending",
    ),
    path(
        "<int:id_payment>/mark-paid/",
        payment_mark_paid_view,
        name="payment_mark_paid",
    ),
    path(
        "<int:id_payment>/verify/",
        payment_verify_view,
        name="payment_verify",
    ),
    path(
        "<int:id_payment>/confirm/",
        payment_confirm_view,
        name="payment_confirm",
    ),
    path(
        "<int:id_payment>/reject/",
        payment_reject_view,
        name="payment_reject",
    ),
    path(
        "<int:id_payment>/cancel/",
        payment_cancel_view,
        name="payment_cancel",
    ),
    path(
        "<int:id_payment>/void/",
        payment_void_view,
        name="payment_void",
    ),
    path("api/", include(router.urls)),
]