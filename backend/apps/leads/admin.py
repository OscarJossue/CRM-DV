from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id_lead",
        "name",
        "id_company",
        "id_assigned_user",
        "status",
        "source",
        "id_converted_client",
        "created_at",
    )
    list_filter = (
        "id_company",
        "status",
        "source",
        "created_at",
    )
    search_fields = (
        "name",
        "phone",
        "email",
        "source",
        "id_company__name",
        "id_assigned_user__email",
    )
    readonly_fields = ("created_at",)
