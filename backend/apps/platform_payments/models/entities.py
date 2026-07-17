from decimal import Decimal

from django.db import models

from .choices import (
    PAYMENT_METHOD_CHOICES,
    PAYMENT_METHOD_MANUAL,
    PAYMENT_STATUS_CHOICES,
    PAYMENT_STATUS_PENDING,
)


class PlatformPayment(models.Model):
    id_payment = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="platform_payments",
    )

    id_subscription = models.ForeignKey(
        "platform_subscriptions.PlatformSubscription",
        db_column="id_subscription",
        on_delete=models.SET_NULL,
        related_name="platform_payments",
        blank=True,
        null=True,
    )

    id_document = models.ForeignKey(
        "platform_documents.PlatformDocument",
        db_column="id_document",
        on_delete=models.SET_NULL,
        related_name="platform_payments",
        blank=True,
        null=True,
    )

    payment_number = models.CharField(max_length=80, unique=True, db_index=True)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    payment_date = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING,
        db_index=True,
    )

    method = models.CharField(
        max_length=40,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_MANUAL,
        db_index=True,
    )

    reference = models.CharField(max_length=180, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    received_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="received_by",
        on_delete=models.SET_NULL,
        related_name="received_platform_payments",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_payment"
        ordering = ["-payment_date", "-id_payment"]
        indexes = [
            models.Index(fields=["payment_number"], name="platform_pay_number_idx"),
            models.Index(fields=["status"], name="platform_pay_status_idx"),
            models.Index(fields=["method"], name="platform_pay_method_idx"),
            models.Index(fields=["payment_date"], name="platform_pay_date_idx"),
        ]

    def __str__(self):
        return f"{self.payment_number} - {self.id_company.name}"