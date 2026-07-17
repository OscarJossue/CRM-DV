from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import (
    CREDIT_MOVEMENT_TYPE_CHOICES,
    FINANCIAL_MOVEMENT_TYPE_CHOICES,
    PAYMENT_METHOD_CASH,
    PAYMENT_METHOD_CHOICES,
    PAYMENT_STATUS_CHOICES,
    PAYMENT_STATUS_PENDING_PAYMENT,
    PAYMENT_STATUS_VOID,
)


class Payment(models.Model):
    id_payment = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )

    # Legacy/main invoice relation.
    # New workflow uses PaymentAllocation for one payment -> many invoices.
    id_invoice = models.ForeignKey(
        "invoices.Invoice",
        db_column="id_invoice",
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="payments",
        blank=True,
        null=True,
    )

    payment_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    # Voucher is no longer globally unique because voided payments may reuse it.
    # Uniqueness is controlled by a conditional constraint below.
    voucher_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    reference_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Receipt, check, bank transfer, Zelle, ACH or external confirmation code.",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    payment_method = models.CharField(
        max_length=100,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_CASH,
        blank=True,
        null=True,
    )

    receipt_file = models.FileField(
        upload_to="payment_receipts/",
        blank=True,
        null=True,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    payment_date = models.DateField(
        default=timezone.localdate,
    )

    status = models.CharField(
        max_length=50,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING_PAYMENT,
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="verified_by",
        on_delete=models.SET_NULL,
        related_name="verified_payments",
        blank=True,
        null=True,
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_payments",
        blank=True,
        null=True,
    )

    voided_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    void_reason = models.TextField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payments",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    updated_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "payment"
        ordering = ["-payment_date", "-id_payment"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "payment_number"],
                condition=(
                    models.Q(payment_number__isnull=False)
                    & ~models.Q(payment_number="")
                ),
                name="unique_payment_number_per_company",
            ),
            models.UniqueConstraint(
                fields=["id_company", "voucher_code"],
                condition=(
                    models.Q(voucher_code__isnull=False)
                    & ~models.Q(voucher_code="")
                    & ~models.Q(status=PAYMENT_STATUS_VOID)
                ),
                name="unique_active_payment_voucher_per_company",
            ),
            models.UniqueConstraint(
                fields=["id_company", "reference_code"],
                condition=(
                    models.Q(reference_code__isnull=False)
                    & ~models.Q(reference_code="")
                    & ~models.Q(status=PAYMENT_STATUS_VOID)
                ),
                name="unique_active_payment_reference_per_company",
            ),
        ]

    def __str__(self):
        return self.payment_number or self.voucher_code or f"Payment {self.id_payment}"

    @property
    def allocated_amount(self):
        total = Decimal("0.00")

        if not self.pk:
            return total

        for allocation in self.allocations.all():
            total += allocation.amount or Decimal("0.00")

        return total

    @property
    def available_amount(self):
        available = (self.amount or Decimal("0.00")) - self.allocated_amount

        if available < Decimal("0.00"):
            return Decimal("0.00")

        return available


class PaymentAllocation(models.Model):
    id_payment_allocation = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="payment_allocations",
        blank=True,
        null=True,
    )

    id_payment = models.ForeignKey(
        Payment,
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="allocations",
    )

    id_invoice = models.ForeignKey(
        "invoices.Invoice",
        db_column="id_invoice",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    allocated_at = models.DateTimeField(
        default=timezone.now,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payment_allocations",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "payment_allocation"
        ordering = ["id_payment_allocation"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_payment", "id_invoice"],
                name="unique_invoice_allocation_per_payment",
            ),
        ]

    def __str__(self):
        return f"{self.id_payment} -> {self.id_invoice} - {self.amount}"


class ClientCreditAccount(models.Model):
    id_credit_account = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="client_credit_accounts",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="credit_accounts",
    )

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    updated_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "client_credit_account"
        ordering = ["id_client"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "id_client"],
                name="unique_credit_account_per_company_client",
            ),
        ]

    def __str__(self):
        return f"{self.id_client} credit balance: {self.balance}"


class ClientCreditMovement(models.Model):
    id_credit_movement = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="client_credit_movements",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="credit_movements",
    )

    id_payment = models.ForeignKey(
        Payment,
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="credit_movements",
        blank=True,
        null=True,
    )

    id_invoice = models.ForeignKey(
        "invoices.Invoice",
        db_column="id_invoice",
        on_delete=models.PROTECT,
        related_name="credit_movements",
        blank=True,
        null=True,
    )

    movement_type = models.CharField(
        max_length=50,
        choices=CREDIT_MOVEMENT_TYPE_CHOICES,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    movement_date = models.DateField(
        default=timezone.localdate,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_credit_movements",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "client_credit_movement"
        ordering = ["-movement_date", "-id_credit_movement"]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.id_client} - {self.amount}"


class FinancialMovement(models.Model):
    id_financial_movement = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="financial_movements",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="financial_movements",
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.PROTECT,
        related_name="financial_movements",
        blank=True,
        null=True,
    )

    id_invoice = models.ForeignKey(
        "invoices.Invoice",
        db_column="id_invoice",
        on_delete=models.PROTECT,
        related_name="financial_movements",
        blank=True,
        null=True,
    )

    id_payment = models.ForeignKey(
        Payment,
        db_column="id_payment",
        on_delete=models.PROTECT,
        related_name="financial_movements",
        blank=True,
        null=True,
    )

    movement_type = models.CharField(
        max_length=50,
        choices=FINANCIAL_MOVEMENT_TYPE_CHOICES,
    )

    movement_date = models.DateField(
        default=timezone.localdate,
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    debit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount that increases client debt.",
    )

    credit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount that reduces client debt.",
    )

    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_financial_movements",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "financial_movement"
        ordering = ["-movement_date", "-id_financial_movement"]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.id_client}"