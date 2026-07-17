from django.contrib import admin

from .models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "id_contract",
        "id_client",
        "id_project",
        "status",
        "signed_date",
    )
    search_fields = (
        "id_client__name",
        "id_project__name",
        "id_project__id_company__name",
        "terms",
    )
    list_filter = (
        "status",
        "signed_date",
        "id_project__id_company",
    )
