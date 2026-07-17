from django.db import models

from .choices import (
    EVENT_PRIORITY_CHOICES,
    EVENT_PRIORITY_NORMAL,
    EVENT_STATUS_CHOICES,
    EVENT_STATUS_SCHEDULED,
    EVENT_TYPE_CHOICES,
    EVENT_TYPE_MANUAL,
)


class PlatformCalendarEvent(models.Model):
    id_event = models.BigAutoField(primary_key=True)

    title = models.CharField(max_length=180)
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        default=EVENT_TYPE_MANUAL,
        db_index=True,
    )

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.SET_NULL,
        related_name="platform_calendar_events",
        blank=True,
        null=True,
    )

    id_subscription = models.ForeignKey(
        "platform_subscriptions.PlatformSubscription",
        db_column="id_subscription",
        on_delete=models.SET_NULL,
        related_name="platform_calendar_events",
        blank=True,
        null=True,
    )

    start_date = models.DateField(db_index=True)
    start_time = models.TimeField(blank=True, null=True)

    end_date = models.DateField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=EVENT_STATUS_CHOICES,
        default=EVENT_STATUS_SCHEDULED,
        db_index=True,
    )

    priority = models.CharField(
        max_length=30,
        choices=EVENT_PRIORITY_CHOICES,
        default=EVENT_PRIORITY_NORMAL,
        db_index=True,
    )

    description = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        "accounts.UserAccount",
        db_column="created_by",
        on_delete=models.SET_NULL,
        related_name="created_platform_calendar_events",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_calendar_event"
        ordering = ["start_date", "start_time", "title"]
        indexes = [
            models.Index(fields=["event_type"], name="platform_cal_type_idx"),
            models.Index(fields=["status"], name="platform_cal_status_idx"),
            models.Index(fields=["priority"], name="platform_cal_priority_idx"),
            models.Index(fields=["start_date"], name="platform_cal_start_idx"),
        ]

    def __str__(self):
        return self.title