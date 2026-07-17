from django.db import models

from .choices import (
    NOTIFICATION_CHANNEL_CHOICES,
    NOTIFICATION_CHANNEL_EMAIL,
    NOTIFICATION_STATUS_CHOICES,
    NOTIFICATION_STATUS_PENDING,
    NOTIFICATION_TYPE_CHOICES,
    NOTIFICATION_TYPE_RENEWAL_REMINDER,
)


class PlatformNotificationLog(models.Model):
    id_notification = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="platform_notification_logs",
    )

    id_subscription = models.ForeignKey(
        "platform_subscriptions.PlatformSubscription",
        db_column="id_subscription",
        on_delete=models.SET_NULL,
        related_name="platform_notification_logs",
        blank=True,
        null=True,
    )

    notification_type = models.CharField(
        max_length=60,
        choices=NOTIFICATION_TYPE_CHOICES,
        default=NOTIFICATION_TYPE_RENEWAL_REMINDER,
        db_index=True,
    )

    channel = models.CharField(
        max_length=30,
        choices=NOTIFICATION_CHANNEL_CHOICES,
        default=NOTIFICATION_CHANNEL_EMAIL,
        db_index=True,
    )

    recipient_email = models.EmailField(max_length=180)
    subject = models.CharField(max_length=255)
    message = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=NOTIFICATION_STATUS_CHOICES,
        default=NOTIFICATION_STATUS_PENDING,
        db_index=True,
    )

    scheduled_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="created_by",
        on_delete=models.SET_NULL,
        related_name="created_platform_notifications",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_notification_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["notification_type"], name="platform_notif_type_idx"),
            models.Index(fields=["channel"], name="platform_notif_channel_idx"),
            models.Index(fields=["status"], name="platform_notif_status_idx"),
            models.Index(fields=["created_at"], name="platform_notif_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.id_company.name}"