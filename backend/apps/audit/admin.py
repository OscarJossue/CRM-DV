from django.contrib import admin

from .models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = (
        "id_log",
        "id_company",
        "actor_email",
        "module",
        "action_type",
        "object_label",
        "severity",
        "ip",
        "created_at",
        "expires_at",
    )
    search_fields = (
        "id_company__name",
        "actor_name",
        "actor_email",
        "module",
        "action",
        "object_type",
        "object_label",
        "object_id",
        "ip",
    )
    list_filter = ("id_company", "module", "action_type", "severity", "created_at")
    readonly_fields = tuple(field.name for field in SystemLog._meta.fields)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
