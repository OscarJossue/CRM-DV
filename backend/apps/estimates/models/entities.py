import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import ESTIMATE_STATUS_CHOICES, ESTIMATE_STATUS_PENDING_SEND


class Estimate(models.Model):
    id_estimate = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="estimates",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.CASCADE,
        related_name="estimates",
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="estimates",
        blank=True,
        null=True,
    )

    id_inspection_assignment = models.ForeignKey(
        "inspections.InspectionAssignment",
        db_column="id_inspection_assignment",
        on_delete=models.SET_NULL,
        related_name="estimates",
        blank=True,
        null=True,
    )

    # New financial estimate number.
    # Nullable for old records already created before this merge.
    estimate_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    # Legacy JSON items from the base project.
    # Keep this field temporarily so current forms/views/templates do not break.
    detail_items = models.JSONField(
        default=list,
        blank=True,
    )

    logo = models.TextField(blank=True, null=True)
    pdf_header_dark = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    # Billing snapshot
    client_billing_name = models.CharField(max_length=255, blank=True, null=True)
    client_billing_email = models.EmailField(blank=True, null=True)
    client_billing_phone = models.CharField(max_length=50, blank=True, null=True)
    client_billing_address = models.TextField(blank=True, null=True)

    # Project snapshot
    project_name = models.CharField(max_length=255, blank=True, null=True)
    project_address = models.TextField(blank=True, null=True)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    tax_enabled = models.BooleanField(default=False)

    tax_rate = models.DecimalField(
        max_digits=5,
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

    validity_days = models.PositiveIntegerField(default=15)
    issue_date = models.DateField(default=timezone.now)
    expiration_date = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=50,
        choices=ESTIMATE_STATUS_CHOICES,
        default=ESTIMATE_STATUS_PENDING_SEND,
    )

    # Public customer approval / rejection flow.
    # This token is sent to the customer in the estimate email and does not
    # require a CRM login. When a rejected estimate is edited and resent,
    # the token is regenerated so the old customer decision link is disabled.
    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    public_token_refreshed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    viewed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    rejected_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    rejection_reason = models.TextField(
        blank=True,
        default="",
    )

    notes = models.TextField(blank=True, null=True)

    sent_at = models.DateTimeField(blank=True, null=True)

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="sent_estimates",
    )

    converted_at = models.DateTimeField(blank=True, null=True)

    converted_invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="converted_estimates",
    )

    last_modified_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_estimates",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_estimates",
    )

    class Meta:
        db_table = "estimate"
        ordering = ["-issue_date", "-id_estimate"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "estimate_number"],
                condition=models.Q(estimate_number__isnull=False),
                name="unique_estimate_number_per_company",
            )
        ]

    def __str__(self):
        return self.estimate_number or f"Estimate {self.id_estimate}"


class EstimateItem(models.Model):
    id_estimate_item = models.BigAutoField(primary_key=True)

    id_estimate = models.ForeignKey(
        Estimate,
        db_column="id_estimate",
        on_delete=models.CASCADE,
        related_name="items",
    )

    description = models.TextField()

    photo = models.ImageField(
        upload_to="estimates/items/",
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

    class Meta:
        db_table = "estimate_item"
        ordering = ["id_estimate_item"]

    def __str__(self):
        return f"Item {self.id_estimate_item} - {self.id_estimate}"