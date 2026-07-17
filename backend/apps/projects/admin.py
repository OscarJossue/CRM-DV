from django.contrib import admin

from .models import (
    Project,
    ProjectAssignment,
    ProjectEvidence,
    ProjectNote,
)


class ProjectAssignmentInline(admin.TabularInline):
    model = ProjectAssignment
    extra = 0
    fields = (
        "id_user",
        "task",
        "progress",
        "status",
        "assigned_at",
    )
    readonly_fields = (
        "assigned_at",
    )


class ProjectNoteInline(admin.TabularInline):
    model = ProjectNote
    extra = 0
    fields = (
        "note",
        "created_by",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )


class ProjectEvidenceInline(admin.TabularInline):
    """Read-only evidence received from the contractor field workspace."""

    model = ProjectEvidence
    extra = 0
    can_delete = False
    fields = (
        "title",
        "file",
        "description",
        "uploaded_by",
        "uploaded_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "id_project",
        "project_code",
        "name",
        "id_company",
        "id_client",
        "id_opportunity",
        "id_inspector",
        "invoice_status",
        "status",
        "progress",
        "contract_amount",
        "start_date",
        "end_date",
        "created_at",
    )

    search_fields = (
        "project_code",
        "name",
        "project_address",
        "id_client__name",
        "id_company__name",
        "id_inspector__email",
    )

    list_filter = (
        "id_company",
        "invoice_status",
        "status",
        "created_at",
    )

    readonly_fields = (
        "project_code",
        "created_at",
        "updated_at",
    )

    inlines = [
        ProjectAssignmentInline,
        ProjectNoteInline,
        ProjectEvidenceInline,
    ]


@admin.register(ProjectAssignment)
class ProjectAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id_assignment",
        "id_project",
        "id_user",
        "status",
        "progress",
        "assigned_at",
    )

    search_fields = (
        "id_project__name",
        "id_user__email",
        "id_user__first_name",
        "id_user__last_name",
    )

    list_filter = (
        "status",
        "assigned_at",
    )

    readonly_fields = (
        "assigned_at",
    )


@admin.register(ProjectNote)
class ProjectNoteAdmin(admin.ModelAdmin):
    list_display = (
        "id_project_note",
        "id_project",
        "created_by",
        "created_at",
    )

    search_fields = (
        "id_project__name",
        "note",
        "created_by__email",
    )

    list_filter = (
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(ProjectEvidence)
class ProjectEvidenceAdmin(admin.ModelAdmin):
    """Evidence is visible for audit, but never created or deleted manually."""

    list_display = (
        "id_project_evidence",
        "id_project",
        "title",
        "uploaded_by",
        "uploaded_at",
    )

    search_fields = (
        "id_project__name",
        "title",
        "description",
        "uploaded_by__email",
    )

    list_filter = (
        "uploaded_at",
    )

    readonly_fields = (
        "id_project",
        "title",
        "file",
        "description",
        "uploaded_by",
        "uploaded_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
