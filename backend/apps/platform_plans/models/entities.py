from django.db import models

from .choices import (
    BILLING_CUSTOM,
    BILLING_CYCLE_CHOICES,
    BILLING_MONTHLY,
    CUSTOM_CYCLE_UNIT_CHOICES,
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_CHOICES,
)


class PlatformPlan(models.Model):
    id_plan = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=120, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    billing_cycle = models.CharField(
        max_length=30,
        choices=BILLING_CYCLE_CHOICES,
        default=BILLING_MONTHLY,
        db_index=True,
    )

    custom_cycle_count = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Used only when billing cycle is Custom.",
    )

    custom_cycle_unit = models.CharField(
        max_length=20,
        choices=CUSTOM_CYCLE_UNIT_CHOICES,
        blank=True,
        null=True,
        help_text="Used only when billing cycle is Custom.",
    )

    max_users = models.PositiveIntegerField(default=5)

    status = models.CharField(
        max_length=30,
        choices=PLAN_STATUS_CHOICES,
        default=PLAN_STATUS_ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_plan"
        ordering = ["price", "name"]
        indexes = [
            models.Index(fields=["code"], name="platform_plan_code_idx"),
            models.Index(fields=["status"], name="platform_plan_status_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active_plan(self):
        return self.status == PLAN_STATUS_ACTIVE

    @property
    def billing_cycle_display_label(self):
        if self.billing_cycle != BILLING_CUSTOM:
            return self.get_billing_cycle_display()

        if not self.custom_cycle_count or not self.custom_cycle_unit:
            return "Custom"

        unit = self.get_custom_cycle_unit_display()

        return f"Every {self.custom_cycle_count} {unit.lower()}"