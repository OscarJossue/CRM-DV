from django.contrib import admin

from .models import Inspection, InspectionAssignment


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = (
        "id_inspection",
        "id_project",
        "id_inspector",
        "status",
        "estimated_time",
        "inspection_date",
        "created_at",
    )

    search_fields = (
        "id_project__name",
        "id_project__project_code",
        "id_project__id_client__name",
        "id_project__id_company__name",
        "id_inspector__email",
        "damage_description",
        "materials",
    )

    list_filter = (
        "status",
        "inspection_date",
        "created_at",
        "id_project__id_company",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

@admin.register(InspectionAssignment)
class InspectionAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id_assignment",
        "client",
        "inspector",
        "status",
        "inspection_date",
        "created_at",
    )

    search_fields = (
        "client__name",
        "client__client_code",
        "client__phone",
        "client__email",
        "client__id_company__name",
        "inspector__email",
        "inspector__first_name",
        "inspector__last_name",
        "notes",
    )

    list_filter = (
        "status",
        "inspection_date",
        "created_at",
        "client__id_company",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )