from decimal import Decimal
from urllib.parse import quote_plus

from django.db import models

from .choices import PROJECT_STATUS_CHOICES, PROJECT_STATUS_DRAFT


PROJECT_INVOICE_STATUS_NO_INVOICE = "no_invoice"
PROJECT_INVOICE_STATUS_ATTACHED = "invoice_attached"

PROJECT_INVOICE_STATUS_CHOICES = [
    (PROJECT_INVOICE_STATUS_NO_INVOICE, "No Invoice"),
    (PROJECT_INVOICE_STATUS_ATTACHED, "Invoice Attached"),
]


class Project(models.Model):
    id_project = models.BigAutoField(primary_key=True)

    project_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
    )

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="projects",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.CASCADE,
        related_name="projects",
    )

    id_opportunity = models.ForeignKey(
        "opportunities.Lead",
        db_column="id_opportunity",
        on_delete=models.SET_NULL,
        related_name="projects",
        blank=True,
        null=True,
    )

    id_inspector = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_inspector",
        on_delete=models.SET_NULL,
        related_name="inspected_projects",
        blank=True,
        null=True,
    )

    invoice_status = models.CharField(
        max_length=30,
        choices=PROJECT_INVOICE_STATUS_CHOICES,
        default=PROJECT_INVOICE_STATUS_NO_INVOICE,
    )

    name = models.CharField(
        max_length=255,
    )

    project_address = models.TextField(
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )
    project_notes = models.TextField(blank=True, null=True)

    contractor_observations = models.TextField(
        blank=True,
        null=True,
    )

    contractor_recommendations = models.TextField(
        blank=True,
        null=True,
    )

    google_maps_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        choices=PROJECT_STATUS_CHOICES,
        default=PROJECT_STATUS_DRAFT,
    )

    progress = models.PositiveIntegerField(
        default=0,
    )

    contract_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    start_date = models.DateField(
        blank=True,
        null=True,
    )

    end_date = models.DateField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="created_by_id",
        on_delete=models.SET_NULL,
        related_name="created_projects",
        blank=True,
        null=True,
    )

    updated_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="updated_by_id",
        on_delete=models.SET_NULL,
        related_name="updated_projects",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    submitted_for_audit_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    audit_completed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    review_notes = models.TextField(
        blank=True,
        null=True,
    )

    reviewed_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="reviewed_by_id",
        on_delete=models.SET_NULL,
        related_name="reviewed_projects",
        blank=True,
        null=True,
    )

    cancellation_reason = models.TextField(
        blank=True,
        null=True,
    )

    cancelled_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="cancelled_by_id",
        on_delete=models.SET_NULL,
        related_name="cancelled_projects",
        blank=True,
        null=True,
    )

    cancelled_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "project"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "id_client"], name="project_company_client_idx"),
            models.Index(fields=["project_code"], name="project_code_idx"),
            models.Index(fields=["status"], name="project_status_idx"),
        ]

    @property
    def project_name(self):
        return self.name

    @project_name.setter
    def project_name(self, value):
        self.name = value

    @property
    def maps_url(self):
        direct_url = (self.google_maps_url or "").strip()
        if direct_url:
            return direct_url

        address = (self.project_address or "").strip()
        if not address and self.id_client_id:
            address = (self.id_client.address or "").strip()
        if not address:
            return ""
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"

    @property
    def expected_end_date(self):
        return self.end_date

    @expected_end_date.setter
    def expected_end_date(self, value):
        self.end_date = value

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new and not self.project_code:
            self.project_code = f"P_{self.id_project:05d}"

            Project.objects.filter(
                id_project=self.id_project,
            ).update(
                project_code=self.project_code,
            )

    def __str__(self):
        if self.project_code:
            return f"{self.project_code} - {self.name}"

        return self.name


class ProjectAssignment(models.Model):
    id_assignment = models.BigAutoField(primary_key=True)

    id_project = models.ForeignKey(
        Project,
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    id_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_user",
        on_delete=models.CASCADE,
        related_name="project_assignments",
        blank=True,
        null=True,
    )

    task = models.TextField(
        blank=True,
        null=True,
    )

    progress = models.PositiveIntegerField(
        default=0,
    )

    status = models.CharField(
        max_length=50,
        default="assigned",
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "project_assignment"
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_project", "id_user"],
                name="unique_project_user_assignment",
            )
        ]

    def __str__(self):
        user_label = self.id_user.email if self.id_user else "Unassigned"
        return f"{self.id_project.name} - {user_label}"


class ProjectNote(models.Model):
    id_project_note = models.BigAutoField(primary_key=True)

    id_project = models.ForeignKey(
        Project,
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="notes",
    )

    note = models.TextField()

    created_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="created_by_id",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="project_notes",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "project_note"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note {self.id_project_note}"


class ProjectEvidence(models.Model):
    id_project_evidence = models.BigAutoField(primary_key=True)

    id_project = models.ForeignKey(
        Project,
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="evidence",
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    file = models.FileField(
        upload_to="project_evidence/",
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    uploaded_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="uploaded_by_id",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="project_evidence_uploads",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "project_evidence"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or f"Evidence {self.id_project_evidence}"


class ProjectGalleryImage(models.Model):
    id_project_gallery_image = models.BigAutoField(primary_key=True)

    project = models.ForeignKey(
        Project,
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )

    stage = models.CharField(
        max_length=20,
        choices=[
            ("before", "Before"),
            ("during", "During"),
            ("after", "After"),
        ],
    )

    image = models.ImageField(
        upload_to="projects/gallery/",
    )

    uploaded_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="uploaded_by_id",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="project_gallery_uploads",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "project_gallery_image"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.project.name} - {self.stage}"