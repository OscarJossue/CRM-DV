from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id_company",
        "name",
        "plan",
        "status",
        "user_limit",
        "created_at",
    )
    search_fields = (
        "name",
        "plan",
        "status",
    )
    list_filter = (
        "status",
        "plan",
    )
    readonly_fields = (
        "created_at",
    )
    ordering = (
        "name",
    )

    def has_add_permission(self, request):
        # New tenants must be provisioned through the two-step company wizard,
        # which atomically creates the administrator, permissions and subscription.
        return False
