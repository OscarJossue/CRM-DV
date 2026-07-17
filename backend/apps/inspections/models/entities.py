from urllib.parse import quote_plus

from django.db import models

from .choices import (
    INSPECTION_STATUS_CHOICES,
    INSPECTION_STATUS_DRAFT,
)


class Inspection(models.Model):
    id_inspection = models.BigAutoField(primary_key=True)

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="inspections",
    )

    id_inspector = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_inspector",
        on_delete=models.SET_NULL,
        related_name="inspections",
        blank=True,
        null=True,
    )

    inspection_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    damage_description = models.TextField(
        blank=True,
        null=True,
    )

    materials = models.TextField(
        blank=True,
        null=True,
    )

    photos = models.TextField(
        blank=True,
        null=True,
    )

    estimated_time = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        choices=INSPECTION_STATUS_CHOICES,
        default=INSPECTION_STATUS_DRAFT,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "inspection"
        ordering = ["-inspection_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["id_project", "status"],
                name="inspection_project_status_idx",
            ),
            models.Index(
                fields=["inspection_date"],
                name="inspection_date_idx",
            ),
        ]

    @property
    def id_company(self):
        if self.id_project_id:
            return self.id_project.id_company

        return None

    @property
    def id_company_id(self):
        if self.id_project_id:
            return self.id_project.id_company_id

        return None

    @property
    def project_name(self):
        if self.id_project_id:
            return self.id_project.project_name

        return "No Project"

    @property
    def client_name(self):
        if self.id_project_id and self.id_project.id_client_id:
            return self.id_project.id_client.name

        return "No Client"

    def __str__(self):
        return f"Inspection #{self.id_inspection} - {self.project_name}"


class InspectionAssignment(models.Model):
    id_assignment = models.BigAutoField(primary_key=True)

    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="source_inspection_assignments",
        blank=True,
        null=True,
    )

    client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.CASCADE,
        related_name="inspection_assignments",
    )

    inspector = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_inspector",
        on_delete=models.SET_NULL,
        related_name="inspection_assignments",
        blank=True,
        null=True,
    )

    inspection_date = models.DateTimeField()

    status = models.CharField(
        max_length=50,
        choices=INSPECTION_STATUS_CHOICES,
        default=INSPECTION_STATUS_DRAFT,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )
    inspection_notes = models.TextField(
        blank=True,
        null=True,
    )

    recommendations = models.TextField(
        blank=True,
        null=True,
    )

    google_maps_url = models.URLField(
        max_length=1000,
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
        related_name="reviewed_inspection_assignments",
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
        related_name="cancelled_inspection_assignments",
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
        db_table = "inspection_assignment"
        ordering = ["-inspection_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["client", "status"],
                name="insp_assign_client_status_idx",
            ),
            models.Index(
                fields=["inspector", "status"],
                name="insp_asg_inspector_idx",
            ),
            models.Index(
                fields=["inspection_date"],
                name="insp_assign_date_idx",
            ),
        ]

    @property
    def id_company(self):
        if self.client_id:
            return self.client.id_company
        return None

    @property
    def id_company_id(self):
        if self.client_id:
            return self.client.id_company_id
        return None

    @property
    def client_name(self):
        if self.client_id:
            return self.client.name
        return "No Client"

    @property
    def maps_url(self):
        direct_url = (self.google_maps_url or "").strip()
        if direct_url:
            return direct_url

        address = ""
        if self.client_id:
            address = (self.client.address or "").strip()
        if not address:
            return ""
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"

    @property
    def inspector_name(self):
        if not self.inspector_id:
            return "No Inspector"

        full_name = f"{self.inspector.first_name or ''} {self.inspector.last_name or ''}".strip()

        return full_name or self.inspector.email

    def __str__(self):
        return f"Inspection Assignment #{self.id_assignment} - {self.client_name}"

class InspectionAssignmentGalleryImage(models.Model):
    CATEGORY_BEFORE = "before"
    CATEGORY_DURING = "during"
    CATEGORY_AFTER = "after"

    CATEGORY_CHOICES = [
        (CATEGORY_BEFORE, "Before"),
        (CATEGORY_DURING, "During"),
        (CATEGORY_AFTER, "After"),
    ]

    id_image = models.BigAutoField(primary_key=True)

    assignment = models.ForeignKey(
        InspectionAssignment,
        db_column="id_assignment",
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_BEFORE,
    )

    file = models.ImageField(
        upload_to="inspection_assignments/gallery/",
    )

    title = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    uploaded_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="uploaded_by",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="inspection_assignment_gallery_uploads",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "inspection_assignment_gallery_image"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.assignment_id} - {self.category}"