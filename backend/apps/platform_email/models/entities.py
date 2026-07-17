from django.db import models

from .choices import EMAIL_STATUS_PENDING, EMAIL_STATUS_CHOICES, EMAIL_TYPE_CHOICES, EMAIL_TYPE_TEST


class PlatformEmailLog(models.Model):
    id_email_log = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.SET_NULL,
        related_name="platform_email_logs",
        blank=True,
        null=True,
    )
    recipient_email = models.EmailField(max_length=180)
    subject = models.CharField(max_length=255)
    email_type = models.CharField(
        max_length=80,
        choices=EMAIL_TYPE_CHOICES,
        default=EMAIL_TYPE_TEST,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=EMAIL_STATUS_CHOICES,
        default=EMAIL_STATUS_PENDING,
        db_index=True,
    )
    message = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_email_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="platform_email_status_idx"),
            models.Index(fields=["email_type"], name="platform_email_type_idx"),
        ]

    def __str__(self):
        return f"{self.recipient_email} - {self.subject}"