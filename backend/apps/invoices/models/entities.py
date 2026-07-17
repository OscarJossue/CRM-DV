from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import (
    INVOICE_PAYMENT_STATUS_CHOICES,
    INVOICE_PAYMENT_STATUS_UNPAID,
    INVOICE_STATUS_CHOICES,
    INVOICE_STATUS_DRAFT,
)


class Invoice(models.Model):
    id_invoice = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="invoices",
        blank=True,
        null=True,
    )

    id_estimate = models.OneToOneField(
        "estimates.Estimate",
        db_column="id_estimate",
        on_delete=models.SET_NULL,
        related_name="invoice",
        blank=True,
        null=True,
    )

    invoice_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    # Legacy JSON items from companion base.
    # Keep this field temporarily so old records/templates/API do not break.
    detail_items = models.JSONField(default=list, blank=True)

    # Billing snapshot.
    client_billing_name = models.CharField(max_length=255, blank=True, null=True)
    client_billing_email = models.EmailField(blank=True, null=True)
    client_billing_phone = models.CharField(max_length=50, blank=True, null=True)
    client_billing_dni = models.CharField(max_length=50, blank=True, null=True)
    client_billing_address = models.TextField(blank=True, null=True)

    # Project snapshot.
    project_name = models.CharField(max_length=255, blank=True, null=True)
    project_address = models.TextField(blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    pdf_header_dark = models.BooleanField(default=False)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # Tax is controlled globally at invoice level, not independently per item.
    tax_enabled = models.BooleanField(default=False)

    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # Legacy field compatibility.
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    balance_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    payment_status = models.CharField(
        max_length=30,
        choices=INVOICE_PAYMENT_STATUS_CHOICES,
        default=INVOICE_PAYMENT_STATUS_UNPAID,
    )

    last_payment_at = models.DateTimeField(blank=True, null=True)

    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=50,
        choices=INVOICE_STATUS_CHOICES,
        default=INVOICE_STATUS_DRAFT,
    )

    notes = models.TextField(blank=True, null=True)

    generated_at = models.DateTimeField(blank=True, null=True)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="generated_invoices",
    )

    sent_at = models.DateTimeField(blank=True, null=True)

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="sent_invoices",
    )

    voided_at = models.DateTimeField(blank=True, null=True)

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="voided_invoices",
    )

    void_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_invoices",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_invoices",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice"
        ordering = ["-issue_date", "-id_invoice"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "invoice_number"],
                condition=(
                    models.Q(invoice_number__isnull=False)
                    & ~models.Q(invoice_number="")
                ),
                name="unique_invoice_number_per_company",
            )
        ]

    def __str__(self):
        return self.invoice_number or f"Invoice {self.id_invoice}"


class InvoiceItem(models.Model):
    id_invoice_item = models.BigAutoField(primary_key=True)

    invoice = models.ForeignKey(
        Invoice,
        db_column="id_invoice",
        on_delete=models.CASCADE,
        related_name="items",
    )

    description = models.TextField()

    photo = models.ImageField(
        upload_to="invoices/items/",
        blank=True,
        null=True,
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # Kept for compatibility with existing records/forms.
    # The invoice tax calculation is controlled by Invoice.tax_enabled and Invoice.tax_rate.
    taxable = models.BooleanField(default=True)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_item"
        ordering = ["id_invoice_item"]

    def __str__(self):
        return f"Item {self.id_invoice_item} - {self.invoice}"