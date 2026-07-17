from django.db import models

from .choices import (
    EVENT_CATEGORY_CHOICES,
    EVENT_CATEGORY_TASK,
    EVENT_PRIORITY_CHOICES,
    EVENT_PRIORITY_NORMAL,
    EVENT_STATUS_CHOICES,
    EVENT_STATUS_SCHEDULED,
    RELATED_TYPE_CHOICES,
)


class CalendarEvent(models.Model):
    id_event = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    id_project = models.ForeignKey(
        "projects.Project",
        db_column="id_project",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_inspection_assignment = models.ForeignKey(
        "inspections.InspectionAssignment",
        db_column="id_inspection_assignment",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_estimate = models.ForeignKey(
        "estimates.Estimate",
        db_column="id_estimate",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_invoice = models.ForeignKey(
        "invoices.Invoice",
        db_column="id_invoice",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_payment = models.ForeignKey(
        "payments.Payment",
        db_column="id_payment",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_opportunity = models.ForeignKey(
        "opportunities.Lead",
        db_column="id_opportunity",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    id_assigned_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_assigned_user",
        on_delete=models.SET_NULL,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(
        max_length=30,
        choices=EVENT_CATEGORY_CHOICES,
        default=EVENT_CATEGORY_TASK,
    )
    priority = models.CharField(
        max_length=20,
        choices=EVENT_PRIORITY_CHOICES,
        default=EVENT_PRIORITY_NORMAL,
    )
    related_type = models.CharField(
        max_length=30,
        choices=RELATED_TYPE_CHOICES,
        blank=True,
        default="",
    )
    event_date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=EVENT_STATUS_CHOICES,
        default=EVENT_STATUS_SCHEDULED,
    )

    class Meta:
        db_table = "calendar_event"
        ordering = ["event_date", "start_time", "title"]
        indexes = [
            models.Index(
                fields=["id_company", "event_date"],
                name="calendar_company_date_idx",
            ),
            models.Index(
                fields=["id_assigned_user", "status"],
                name="calendar_assignee_status_idx",
            ),
        ]

    def __str__(self):
        return self.title or f"Event {self.id_event}"

    @property
    def assigned_user_name(self):
        if not self.id_assigned_user_id:
            return "Unassigned"

        full_name = (
            f"{self.id_assigned_user.first_name or ''} "
            f"{self.id_assigned_user.last_name or ''}"
        ).strip()
        return full_name or self.id_assigned_user.email

    @property
    def related_object(self):
        relation_map = {
            "inspection": self.id_inspection_assignment,
            "estimate": self.id_estimate,
            "invoice": self.id_invoice,
            "payment": self.id_payment,
            "client": self.id_client,
            "opportunity": self.id_opportunity,
            "project": self.id_project,
        }
        return relation_map.get(self.related_type)
