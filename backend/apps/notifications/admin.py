from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id_notification",
        "id_user",
        "type",
        "title",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "type",
        "created_at",
    )
    search_fields = (
        "title",
        "message",
        "id_user__email",
        "id_user__first_name",
        "id_user__last_name",
    )
    readonly_fields = ("created_at",)
