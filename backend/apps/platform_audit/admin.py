from django.contrib import admin

from .models import PlatformAuditLog


@admin.register(PlatformAuditLog)
class PlatformAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id_audit",
        "actor_user",
        "id_company",
        "module_name",
        "action",
        "object_id",
        "ip_address",
        "created_at",
    )
    list_filter = ("module_name", "action", "created_at")
    search_fields = (
        "actor_user__email",
        "id_company__name",
        "module_name",
        "action",
        "object_id",
        "object_label",
        "description",
    )
    readonly_fields = (
        "actor_user",
        "id_company",
        "module_name",
        "action",
        "object_id",
        "object_label",
        "description",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    )