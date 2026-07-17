from django.contrib import admin

from .models import PlatformPlan


@admin.register(PlatformPlan)
class PlatformPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id_plan",
        "name",
        "code",
        "price",
        "billing_cycle",
        "max_users",
        "status",
        "created_at",
    )
    list_filter = ("status", "billing_cycle")
    search_fields = ("name", "code")