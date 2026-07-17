import os
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import (
    DOCUMENT_TYPE_CHOICES,
    DOCUMENT_TYPE_RECEIPT,
    OFFER_TYPE_CHOICES,
    OFFER_TYPE_PRODUCT,
    PURCHASE_PAYMENT_STATUS_CHOICES,
    PURCHASE_PAYMENT_STATUS_UNPAID,
    PURCHASE_STATUS_CHOICES,
    PURCHASE_STATUS_DRAFT,
    SUPPLIER_CATEGORY_CHOICES,
    SUPPLIER_CATEGORY_OTHER,
    SUPPLIER_STATUS_ACTIVE,
    SUPPLIER_STATUS_CHOICES,
    SUPPLIER_TYPE_CHOICES,
    SUPPLIER_TYPE_OTHER,
)


def supplier_document_upload_path(instance, filename):
    base_name, extension = os.path.splitext(filename)
    clean_extension = extension.lower()
    company_id = getattr(instance, "id_company_id", None) or "new"
    supplier_id = getattr(instance, "id_supplier_id", None) or "general"
    return f"suppliers/{company_id}/{supplier_id}/{base_name}{clean_extension}"


class Supplier(models.Model):
    id_supplier = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="suppliers",
    )

    supplier_code = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    company_name = models.CharField(max_length=255, db_index=True)
    contact_name = models.CharField(max_length=180, blank=True, null=True)
    email = models.EmailField(max_length=180, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    zip_code = models.CharField(max_length=30, blank=True, null=True)
    country = models.CharField(max_length=120, blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)
    tax_id = models.CharField(max_length=80, blank=True, null=True)
    supplier_type = models.CharField(
        max_length=60,
        choices=SUPPLIER_TYPE_CHOICES,
        default=SUPPLIER_TYPE_OTHER,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=SUPPLIER_STATUS_CHOICES,
        default=SUPPLIER_STATUS_ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_suppliers",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_suppliers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier"
        ordering = ["company_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "supplier_code"],
                condition=(models.Q(supplier_code__isnull=False) & ~models.Q(supplier_code="")),
                name="uniq_sup_code_company",
            ),
            models.UniqueConstraint(
                fields=["id_company", "company_name"],
                name="uniq_sup_name_company",
            ),
        ]
        indexes = [
            models.Index(fields=["id_company", "status"], name="supplier_company_status_idx"),
            models.Index(fields=["id_company", "supplier_type"], name="supplier_company_type_idx"),
            models.Index(fields=["company_name"], name="supplier_company_name_idx"),
        ]

    def __str__(self):
        return self.company_name

    @property
    def is_active_supplier(self):
        return self.status == SUPPLIER_STATUS_ACTIVE


class SupplierOffer(models.Model):
    id_supplier_offer = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="supplier_offers",
    )

    id_supplier = models.ForeignKey(
        Supplier,
        db_column="id_supplier",
        on_delete=models.CASCADE,
        related_name="offers",
    )

    offer_type = models.CharField(
        max_length=50,
        choices=OFFER_TYPE_CHOICES,
        default=OFFER_TYPE_PRODUCT,
        db_index=True,
    )
    name = models.CharField(max_length=255, db_index=True)
    product_code = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    category = models.CharField(
        max_length=60,
        choices=SUPPLIER_CATEGORY_CHOICES,
        default=SUPPLIER_CATEGORY_OTHER,
        db_index=True,
    )
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    estimated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=30,
        choices=SUPPLIER_STATUS_CHOICES,
        default=SUPPLIER_STATUS_ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_supplier_offers",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_supplier_offers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_offer"
        ordering = ["id_supplier__company_name", "name"]
        indexes = [
            models.Index(fields=["id_company", "category"], name="supplier_offer_category_idx"),
            models.Index(fields=["id_company", "status"], name="supplier_offer_status_idx"),
        ]

    def __str__(self):
        return f"{self.name} - {self.id_supplier.company_name}"


class SupplierPurchase(models.Model):
    id_supplier_purchase = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="supplier_purchases",
    )

    id_supplier = models.ForeignKey(
        Supplier,
        db_column="id_supplier",
        on_delete=models.RESTRICT,
        related_name="purchases",
    )

    purchase_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    external_document_number = models.CharField(max_length=120, blank=True, null=True)
    purchase_date = models.DateField(default=timezone.localdate, db_index=True)
    category = models.CharField(
        max_length=60,
        choices=SUPPLIER_CATEGORY_CHOICES,
        default=SUPPLIER_CATEGORY_OTHER,
        db_index=True,
    )
    description = models.TextField(blank=True, null=True)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_amount = models.DecimalField(
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

    status = models.CharField(
        max_length=30,
        choices=PURCHASE_STATUS_CHOICES,
        default=PURCHASE_STATUS_DRAFT,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=30,
        choices=PURCHASE_PAYMENT_STATUS_CHOICES,
        default=PURCHASE_PAYMENT_STATUS_UNPAID,
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_supplier_purchases",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_supplier_purchases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_purchase"
        ordering = ["-purchase_date", "-id_supplier_purchase"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "purchase_number"],
                condition=(models.Q(purchase_number__isnull=False) & ~models.Q(purchase_number="")),
                name="uniq_sup_purch_num_company",
            )
        ]
        indexes = [
            models.Index(fields=["id_company", "status"], name="supplier_purchase_status_idx"),
            models.Index(fields=["id_company", "payment_status"], name="sup_purch_pay_idx"),
            models.Index(fields=["id_company", "purchase_date"], name="supplier_purchase_date_idx"),
        ]

    def __str__(self):
        return self.purchase_number or f"Purchase {self.id_supplier_purchase}"


class SupplierPurchaseItem(models.Model):
    id_supplier_purchase_item = models.BigAutoField(primary_key=True)

    id_purchase = models.ForeignKey(
        SupplierPurchase,
        db_column="id_supplier_purchase",
        on_delete=models.CASCADE,
        related_name="items",
    )

    id_offer = models.ForeignKey(
        SupplierOffer,
        db_column="id_supplier_offer",
        on_delete=models.SET_NULL,
        related_name="purchase_items",
        blank=True,
        null=True,
    )

    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit = models.CharField(max_length=50, blank=True, null=True)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_amount = models.DecimalField(
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
        db_table = "supplier_purchase_item"
        ordering = ["id_supplier_purchase_item"]

    def __str__(self):
        return self.item_name


class SupplierDocument(models.Model):
    id_supplier_document = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="supplier_documents",
    )
    id_supplier = models.ForeignKey(
        Supplier,
        db_column="id_supplier",
        on_delete=models.CASCADE,
        related_name="documents",
        blank=True,
        null=True,
    )
    id_purchase = models.ForeignKey(
        SupplierPurchase,
        db_column="id_supplier_purchase",
        on_delete=models.CASCADE,
        related_name="documents",
        blank=True,
        null=True,
    )

    title = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        default=DOCUMENT_TYPE_RECEIPT,
        db_index=True,
    )
    file = models.FileField(upload_to=supplier_document_upload_path, max_length=500)
    notes = models.TextField(blank=True, null=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uploaded_supplier_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_document"
        ordering = ["-created_at", "-id_supplier_document"]
        indexes = [
            models.Index(fields=["id_company", "document_type"], name="supplier_document_type_idx"),
            models.Index(fields=["id_company", "created_at"], name="supplier_document_date_idx"),
        ]

    def __str__(self):
        return self.title
