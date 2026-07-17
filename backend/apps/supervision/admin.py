from django.contrib import admin

from .models import Supervision


@admin.register(Supervision)
class SupervisionAdmin(admin.ModelAdmin):
    list_display = (
        "id_supervision",
        "id_project",
        "id_supervisor",
        "approved",
        "final_audit",
        "created_at",
    )
    search_fields = (
        "id_project__name",
        "id_project__id_company__name",
        "id_project__id_client__name",
        "id_supervisor__email",
        "observations",
    )
    list_filter = (
        "approved",
        "final_audit",
        "created_at",
        "id_project__id_company",
    )
    readonly_fields = ("created_at",)
