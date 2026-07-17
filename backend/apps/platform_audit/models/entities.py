from django.db import models

from .choices import (
    PLATFORM_AUDIT_ACTION_CHOICES,
    PLATFORM_AUDIT_ACTION_OTHER,
)


class PlatformAuditLog(models.Model):
    id_audit = models.BigAutoField(primary_key=True)

    actor_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="actor_user",
        on_delete=models.SET_NULL,
        related_name="platform_audit_logs",
        blank=True,
        null=True,
    )

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.SET_NULL,
        related_name="platform_audit_logs",
        blank=True,
        null=True,
    )

    module_name = models.CharField(max_length=100, db_index=True)

    action = models.CharField(
        max_length=40,
        choices=PLATFORM_AUDIT_ACTION_CHOICES,
        default=PLATFORM_AUDIT_ACTION_OTHER,
        db_index=True,
    )

    object_id = models.CharField(max_length=120, blank=True, null=True, db_index=True)
    object_label = models.CharField(max_length=255, blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    metadata = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "platform_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["module_name"], name="platform_audit_module_idx"),
            models.Index(fields=["action"], name="platform_audit_action_idx"),
            models.Index(fields=["created_at"], name="platform_audit_created_idx"),
            models.Index(fields=["object_id"], name="platform_audit_object_idx"),
        ]

    def __str__(self):
        actor = self.actor_user.email if self.actor_user else "System"
        return f"{actor} - {self.module_name} - {self.action}"