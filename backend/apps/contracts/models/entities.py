import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import CONTRACT_STATUS_CHOICES, CONTRACT_STATUS_DRAFT


class Contract(models.Model):
    id_contract = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.PROTECT,
        related_name="contracts",
        blank=True,
        null=True,
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.PROTECT,
        related_name="contracts",
    )

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    id_estimate = models.ForeignKey(
        "estimates.Estimate",
        db_column="id_estimate",
        on_delete=models.SET_NULL,
        related_name="contracts",
        blank=True,
        null=True,
    )

    contract_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    contract_title = models.CharField(
        max_length=180,
        blank=True,
        default="Service Contract",
    )

    contract_date = models.DateField(
        default=timezone.localdate,
    )

    expiration_date = models.DateField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        choices=CONTRACT_STATUS_CHOICES,
        default=CONTRACT_STATUS_DRAFT,
    )
    # Public approval / rejection / signature flow

    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    sign_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
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

    sign_token_used_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    sign_token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    signature_image = models.ImageField(
        upload_to="contracts/signatures/",
        blank=True,
        null=True,
    )

    signed_pdf = models.FileField(
        upload_to="contracts/signed/",
        blank=True,
        null=True,
    )

    terms_summary = models.TextField(
        blank=True,
        default=(
            "This contract includes the basic terms and conditions for the project. "
            "For complete terms and conditions, please review the company terms page."
        ),
    )

    terms_url = models.URLField(
        blank=True,
        default="",
    )

    # Company snapshot
    company_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    company_phone = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    company_email = models.EmailField(
        blank=True,
        default="",
    )

    company_address = models.TextField(
        blank=True,
        default="",
    )

    company_license = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    # Client snapshot
    client_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    client_phone = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    client_alt_phone = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    client_email = models.EmailField(
        blank=True,
        default="",
    )

    client_street_address = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    client_city = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    client_state = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    client_zip_code = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    # Project snapshot
    project_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    project_address = models.TextField(
        blank=True,
        default="",
    )

    project_description = models.TextField(
        blank=True,
        default="",
    )

    project_photo = models.ImageField(
        upload_to="contracts/projects/",
        blank=True,
        null=True,
    )

    pdf_header_dark = models.BooleanField(default=False)

    # Contract body based on the physical template
    work_to_be_done = models.TextField(
        blank=True,
        default="",
    )

    additional_work = models.TextField(
        blank=True,
        default="",
    )

    work_not_to_be_done = models.TextField(
        blank=True,
        default="",
    )

    special_instructions = models.TextField(
        blank=True,
        default="",
    )

    consumer_notice = models.TextField(
        blank=True,
        default=(
            "NOTICE TO CONSUMER: You may cancel this contract at any time before "
            "midnight of the third business day after receiving a copy of this contract. "
            "If you wish to cancel this contract, you must either send a signed and dated "
            "written notice of cancellation by registered or certified mail, return receipt requested, "
            "or personally deliver a signed and dated written notice of cancellation."
        ),
    )

    cancellation_notice = models.TextField(
        blank=True,
        default="",
    )

    terms = models.TextField(
        blank=True,
        null=True,
        help_text="Legacy field. Use contract body fields for new contracts.",
    )

    # Financial fields
    contract_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    initial_payment = models.DecimalField(
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

    state_sales_tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    local_sales_tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    state_sales_tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    local_sales_tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total_amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # Signature fields
    company_representative_name = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    company_representative_title = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    customer_signature_name = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    signed_date = models.DateField(
        blank=True,
        null=True,
    )

    company_signed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    customer_signed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # PDF / email control
    file_url = models.TextField(
        blank=True,
        null=True,
        help_text="Legacy field. PDFs are generated on demand.",
    )

    generated_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    sent_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sent_contracts",
        blank=True,
        null=True,
    )

    voided_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_contracts",
        blank=True,
        null=True,
    )

    void_reason = models.TextField(
        blank=True,
        default="",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_contracts",
        blank=True,
        null=True,
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_contracts",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    updated_at = models.DateTimeField(
        default=timezone.now,
    )

    last_modified_at = models.DateTimeField(
        default=timezone.now,
    )
    payment_terms = models.TextField(
        blank=True,
        default="",
    )

    cancellation_terms = models.TextField(
        blank=True,
        default="",
    )

    guarantee_terms = models.TextField(
        blank=True,
        default="",
    )

    miscellaneous_terms = models.TextField(
        blank=True,
        default="",
    )
    class Meta:
        db_table = "contract"
        ordering = ["-id_contract"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_company", "contract_number"],
                condition=(
                    models.Q(contract_number__isnull=False)
                    & ~models.Q(contract_number="")
                ),
                name="unique_contract_number_per_company",
            ),
        ]
        indexes = [
            models.Index(fields=["id_company", "status"]),
            models.Index(fields=["id_company", "id_client"]),
            models.Index(fields=["id_company", "id_project"]),
            models.Index(fields=["id_company", "id_estimate"]),
            models.Index(fields=["contract_number"]),
            models.Index(fields=["public_token"]),
            models.Index(fields=["sign_token"]),
        ]

    def __str__(self):
        return self.contract_number or f"Contract {self.id_contract}"

    @property
    def client_full_address(self):
        parts = [
            self.client_street_address,
            self.client_city,
            self.client_state,
            self.client_zip_code,
        ]

        return ", ".join([part for part in parts if part])

    @property
    def is_draft(self):
        return self.status == "draft"

    @property
    def is_generated(self):
        return self.status == "generated"

    @property
    def is_sent(self):
        return self.status == "sent"

    @property
    def is_signed(self):
        return self.status == "signed"

    @property
    def is_void(self):
        return self.status == "void"
    
    @property
    def is_viewed(self):
        return self.status == "viewed"

    @property
    def is_approved(self):
        return self.status == "approved"

    @property
    def is_rejected(self):
        return self.status == "rejected"

    @property
    def has_used_sign_token(self):
        return bool(self.sign_token_used_at)
class ContractEvidence(models.Model):
    id_contract_evidence = models.BigAutoField(primary_key=True)

    id_contract = models.ForeignKey(
        "contracts.Contract",
        db_column="id_contract",
        related_name="evidence_photos",
        on_delete=models.CASCADE,
    )

    image = models.ImageField(
        upload_to="contracts/evidence/",
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "contract_evidence"
        ordering = ["sort_order", "id_contract_evidence"]

    def __str__(self):
        return f"Evidence {self.id_contract_evidence}"