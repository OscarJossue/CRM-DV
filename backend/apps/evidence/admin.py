from django.contrib import admin

from .models import EvidenceFile


@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = (
        "id_file",
        "id_project",
        "id_user",
        "file_type",
        "created_at",
    )
    search_fields = (
        "id_project__name",
        "id_project__id_company__name",
        "id_project__id_client__name",
        "id_user__email",
        "file_type",
        "description",
    )
    list_filter = (
        "file_type",
        "created_at",
        "id_project__id_company",
    )
    readonly_fields = ("created_at",)
