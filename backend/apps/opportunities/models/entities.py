from django.db import models

from .choices import (
    LEAD_SOURCE_CHOICES,
    OPPORTUNITY_STATUS_CHOICES,
    OPPORTUNITY_STATUS_NEW,
)


class Lead(models.Model):
    id_lead = models.BigAutoField(primary_key=True)

    opportunity_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
    )

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="opportunities",
    )

    id_client = models.ForeignKey(
        "clients.Client",
        db_column="id_client",
        on_delete=models.CASCADE,
        related_name="opportunities",
        blank=True,
        null=True,
    )

    id_assigned_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_assigned_user",
        on_delete=models.SET_NULL,
        related_name="assigned_opportunities",
        blank=True,
        null=True,
    )

    id_converted_project = models.ForeignKey(
        "projects.Project",
        db_column="id_converted_project",
        on_delete=models.SET_NULL,
        related_name="converted_from_opportunities",
        blank=True,
        null=True,
    )

    first_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    middle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    second_last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    contact_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    email = models.EmailField(
        max_length=150,
        blank=True,
        null=True,
    )

    address = models.TextField(
        blank=True,
        null=True,
    )

    source = models.CharField(
        max_length=100,
        choices=LEAD_SOURCE_CHOICES,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        choices=OPPORTUNITY_STATUS_CHOICES,
        default=OPPORTUNITY_STATUS_NEW,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    next_follow_up_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    approximate_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        default=0,
    )

    project_description = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "opportunity"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["id_company", "status"],
                name="opportunity_company_status_idx",
            ),
            models.Index(
                fields=["opportunity_code"],
                name="opportunity_code_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="opportunity_created_idx",
            ),
        ]

    @property
    def name(self):
        if self.contact_name:
            return self.contact_name

        if self.id_client_id:
            return self.id_client.name

        return " ".join(
            filter(
                None,
                [
                    self.first_name,
                    self.middle_name,
                    self.last_name,
                    self.second_last_name,
                ],
            )
        ).strip()

    @property
    def lead_code(self):
        return self.opportunity_code

    def sync_from_client(self):
        if not self.id_client_id:
            return

        client = self.id_client

        self.id_company = client.id_company
        self.first_name = getattr(client, "first_name", None)
        self.middle_name = getattr(client, "middle_name", None)
        self.last_name = getattr(client, "last_name", None)
        self.second_last_name = getattr(client, "second_last_name", None)
        self.phone = client.phone
        self.email = client.email
        self.address = client.address
        self.contact_name = client.name

    def save(self, *args, **kwargs):
        self.sync_from_client()

        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new and not self.opportunity_code:
            self.opportunity_code = f"OPP-{self.id_lead:06d}"

            type(self).objects.filter(
                id_lead=self.id_lead,
            ).update(
                opportunity_code=self.opportunity_code,
            )

    def __str__(self):
        return f"{self.opportunity_code or 'Opportunity'} - {self.name}"


class OpportunityFollowUp(models.Model):
    id_follow_up = models.BigAutoField(primary_key=True)

    id_opportunity = models.ForeignKey(
        "opportunities.Lead",
        db_column="id_opportunity",
        on_delete=models.CASCADE,
        related_name="follow_ups",
    )

    id_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_user",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunity_follow_ups",
    )

    follow_up_type = models.CharField(
        max_length=50,
        choices=[
            ("call", "Call"),
            ("email", "Email"),
            ("text", "Text Message"),
            ("visit", "Visit"),
            ("note", "Note"),
        ],
        default="call",
    )

    note = models.TextField()

    follow_up_date = models.DateTimeField(
        auto_now_add=True,
    )

    next_follow_up_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "opportunity_follow_up"
        ordering = ["-follow_up_date"]

    def __str__(self):
        return f"{self.follow_up_type} - {self.id_opportunity}"