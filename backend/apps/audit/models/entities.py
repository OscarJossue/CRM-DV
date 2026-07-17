from django.core.exceptions import ValidationError
from django.db import models

from .choices import (
    ACTION_SYSTEM,
    ACTION_TYPE_CHOICES,
    RESULT_CHOICES,
    RESULT_SUCCESS,
    SEVERITY_CHOICES,
    SEVERITY_INFO,
)


class SystemLog(models.Model):
    """Immutable, company-scoped operational audit record.

    The table stores compact metadata only. Documents, signatures, credentials,
    long notes and other heavy or sensitive payloads are deliberately excluded.
    """

    id_log = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="system_logs",
    )
    id_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_user",
        on_delete=models.SET_NULL,
        related_name="system_logs",
        blank=True,
        null=True,
    )
    actor_name = models.CharField(max_length=255, blank=True, default="")
    actor_email = models.EmailField(max_length=254, blank=True, default="")
    action = models.CharField(max_length=500, blank=True, null=True)
    action_type = models.CharField(
        max_length=40,
        choices=ACTION_TYPE_CHOICES,
        default=ACTION_SYSTEM,
        db_index=True,
    )
    module = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    object_type = models.CharField(max_length=120, blank=True, default="")
    object_id = models.CharField(max_length=100, blank=True, default="")
    object_label = models.CharField(max_length=255, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_INFO,
        db_index=True,
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default=RESULT_SUCCESS,
    )
    ip = models.CharField(max_length=100, blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    request_id = models.UUIDField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = "system_log"
        ordering = ["-created_at", "-id_log"]
        indexes = [
            models.Index(fields=["id_company", "-created_at"], name="slog_company_created_idx"),
            models.Index(fields=["id_user", "-created_at"], name="slog_user_created_idx"),
            models.Index(fields=["module", "-created_at"], name="slog_module_created_idx"),
            models.Index(fields=["action_type", "-created_at"], name="slog_action_created_idx"),
        ]

    def __str__(self):
        actor = self.actor_email or "System"
        target = self.object_label or self.module or "CRM"
        return f"{actor} · {self.get_action_type_display()} · {target}"

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.pop("allow_audit_update", False):
            raise ValidationError("Audit records are immutable.")
        return super().save(*args, **kwargs)

    @property
    def actor_display(self):
        if self.actor_name and self.actor_email:
            return f"{self.actor_name} · {self.actor_email}"
        return self.actor_name or self.actor_email or "System"

    @property
    def target_display(self):
        if self.object_type and self.object_label:
            return f"{self.object_type} · {self.object_label}"
        return self.object_label or self.object_type or self.module or "CRM"
