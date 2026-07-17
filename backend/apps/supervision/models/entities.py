from django.core.exceptions import ValidationError
from django.db import models


class Supervision(models.Model):
    """Audit queue item for either a project or an assigned inspection."""

    id_supervision = models.BigAutoField(primary_key=True)
    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.CASCADE,
        related_name="supervisions",
        blank=True,
        null=True,
    )
    id_inspection_assignment = models.ForeignKey(
        "inspections.InspectionAssignment",
        db_column="id_inspection_assignment",
        on_delete=models.CASCADE,
        related_name="supervisions",
        blank=True,
        null=True,
    )
    id_supervisor = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_supervisor",
        on_delete=models.SET_NULL,
        related_name="supervisions",
        blank=True,
        null=True,
    )
    observations = models.TextField(blank=True, null=True)
    approved = models.BooleanField(default=False)
    rejected = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True, default="")
    final_audit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supervision"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["approved", "final_audit", "rejected"], name="supervision_status_idx"),
            models.Index(fields=["id_supervisor"], name="supervision_supervisor_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(id_project__isnull=False, id_inspection_assignment__isnull=True)
                    | models.Q(id_project__isnull=True, id_inspection_assignment__isnull=False)
                ),
                name="supervision_exactly_one_target_ck",
            ),
            models.CheckConstraint(
                condition=~models.Q(approved=True, rejected=True),
                name="supervision_not_approved_and_rejected_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(final_audit=False) | models.Q(approved=True, rejected=False),
                name="supervision_final_requires_approved_ck",
            ),
        ]

    def clean(self):
        super().clean()
        target_count = int(bool(self.id_project_id)) + int(bool(self.id_inspection_assignment_id))
        if target_count != 1:
            raise ValidationError("Audit must be linked to exactly one project or inspection.")

        if self.final_audit and not self.approved:
            raise ValidationError("Final audit requires approval first.")

        if self.approved and self.rejected:
            raise ValidationError("An audit cannot be approved and rejected at the same time.")

        company_id = self.company_id
        if self.id_supervisor_id and company_id and self.id_supervisor.id_company_id != company_id:
            raise ValidationError("Supervisor must belong to the same company as the audited record.")

    @property
    def company_id(self):
        if self.id_project_id:
            return self.id_project.id_company_id
        if self.id_inspection_assignment_id:
            return self.id_inspection_assignment.id_company_id
        return None

    @property
    def company(self):
        if self.id_project_id:
            return self.id_project.id_company
        if self.id_inspection_assignment_id:
            return self.id_inspection_assignment.id_company
        return None

    @property
    def client(self):
        if self.id_project_id:
            return self.id_project.id_client
        if self.id_inspection_assignment_id:
            return self.id_inspection_assignment.client
        return None

    @property
    def target_type(self):
        return "project" if self.id_project_id else "inspection"

    @property
    def target(self):
        return self.id_project or self.id_inspection_assignment

    @property
    def target_code(self):
        if self.id_project_id:
            return self.id_project.project_code or f"P_{self.id_project_id:05d}"
        return f"INS-{self.id_inspection_assignment_id:05d}"

    @property
    def target_name(self):
        if self.id_project_id:
            return self.id_project.name
        return f"Inspection - {self.id_inspection_assignment.client_name}"

    @property
    def status(self):
        if self.final_audit:
            return "final_audit"
        if self.rejected:
            return "rejected"
        if self.approved:
            return "approved"
        return "pending"

    def __str__(self):
        return f"Audit {self.id_supervision} - {self.target_code}"
