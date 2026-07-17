from django.contrib import admin

from .models import PlatformEmailLog


@admin.register(PlatformEmailLog)
class PlatformEmailLogAdmin(admin.ModelAdmin):
    list_display = ("id_email_log", "id_company", "recipient_email", "email_type", "status", "sent_at", "created_at")
    list_filter = ("status", "email_type", "created_at")
    search_fields = ("recipient_email", "subject", "id_company__name")