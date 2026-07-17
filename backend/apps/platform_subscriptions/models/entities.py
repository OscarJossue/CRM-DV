from django.db import models

from .choices import SUBSCRIPTION_ACTIVE, SUBSCRIPTION_STATUS_CHOICES


class PlatformSubscription(models.Model):
    id_subscription = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="platform_subscriptions",
    )
    id_plan = models.ForeignKey(
        "platform_plans.PlatformPlan",
        db_column="id_plan",
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=30,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default=SUBSCRIPTION_ACTIVE,
        db_index=True,
    )
    start_date = models.DateField()
    renewal_date = models.DateField(blank=True, null=True, db_index=True)
    end_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_subscription"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="platform_sub_status_idx"),
            models.Index(fields=["renewal_date"], name="platform_sub_renew_idx"),
        ]

    def __str__(self):
        return f"{self.id_company.name} - {self.id_plan.name}"

    @property
    def is_active_subscription(self):
        return self.status == SUBSCRIPTION_ACTIVE