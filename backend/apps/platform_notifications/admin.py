from django.contrib import admin

from .models import PlatformNotificationLog


@admin.register(PlatformNotificationLog)
class PlatformNotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id_notification",
        "id_company",
        "notification_type",
        "channel",
        "recipient_email",
        "status",
        "sent_at",
        "created_at",
    )
    list_filter = ("notification_type", "channel", "status", "created_at")
    search_fields = ("id_company__name", "recipient_email", "subject", "message")