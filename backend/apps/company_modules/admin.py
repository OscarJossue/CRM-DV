from django.contrib import admin

from .models import CompanyModule


@admin.register(CompanyModule)
class CompanyModuleAdmin(admin.ModelAdmin):
    list_display = (
        "id_company_module",
        "id_company",
        "module",
        "is_enabled",
        "created_at",
    )
    search_fields = (
        "id_company__name",
        "module",
    )
    list_filter = (
        "id_company",
        "module",
        "is_enabled",
    )
    readonly_fields = (
        "created_at",
    )
