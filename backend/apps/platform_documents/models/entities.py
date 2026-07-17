from decimal import Decimal

from django.db import models

from .choices import (
    DOCUMENT_STATUS_CHOICES,
    DOCUMENT_STATUS_DRAFT,
    DOCUMENT_TYPE_CHOICES,
    DOCUMENT_TYPE_PROFORMA,
)


class PlatformDocument(models.Model):
    id_document = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="platform_documents",
    )
    id_subscription = models.ForeignKey(
        "platform_subscriptions.PlatformSubscription",
        db_column="id_subscription",
        on_delete=models.SET_NULL,
        related_name="platform_documents",
        blank=True,
        null=True,
    )
    source_document = models.ForeignKey(
        "self",
        db_column="source_document",
        on_delete=models.SET_NULL,
        related_name="generated_documents",
        blank=True,
        null=True,
    )
    document_number = models.CharField(max_length=80, unique=True, db_index=True)
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        default=DOCUMENT_TYPE_PROFORMA,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=DOCUMENT_STATUS_CHOICES,
        default=DOCUMENT_STATUS_DRAFT,
        db_index=True,
    )
    issue_date = models.DateField()
    due_date = models.DateField(blank=True, null=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    notes = models.TextField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    footer = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="created_by",
        on_delete=models.SET_NULL,
        related_name="created_platform_documents",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_document"
        ordering = ["-issue_date", "-id_document"]
        indexes = [
            models.Index(fields=["document_type"], name="platform_doc_type_idx"),
            models.Index(fields=["status"], name="platform_doc_status_idx"),
            models.Index(fields=["issue_date"], name="platform_doc_issue_idx"),
            models.Index(fields=["due_date"], name="platform_doc_due_idx"),
        ]

    def __str__(self):
        return f"{self.document_number} - {self.id_company.name}"


class PlatformDocumentItem(models.Model):
    id_document_item = models.BigAutoField(primary_key=True)
    id_document = models.ForeignKey(
        PlatformDocument,
        db_column="id_document",
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "platform_document_item"
        ordering = ["id_document_item"]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(str(self.quantity or 0)) * Decimal(str(self.unit_price or 0))
        super().save(*args, **kwargs)