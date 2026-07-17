from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, RolePermission, UserAccount


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "id_role",
        "name",
        "id_company",
        "permissions_count",
    )
    search_fields = (
        "name",
        "id_company__name",
    )
    list_filter = (
        "id_company",
    )

    def permissions_count(self, obj):
        return obj.permissions.count()

    permissions_count.short_description = "Permissions"


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = (
        "id_permission",
        "id_role",
        "module",
        "can_view",
        "can_create",
        "can_edit",
        "can_delete",
        "can_approve",
    )
    list_filter = (
        "module",
        "can_view",
        "can_create",
        "can_edit",
        "can_delete",
        "can_approve",
    )
    search_fields = (
        "id_role__name",
        "id_role__id_company__name",
        "module",
    )


@admin.register(UserAccount)
class UserAccountAdmin(UserAdmin):
    model = UserAccount

    list_display = (
        "id_user",
        "email",
        "first_name",
        "last_name",
        "id_company",
        "id_role",
        "status",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "status",
        "is_active",
        "is_staff",
        "is_superuser",
        "id_company",
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
        "phone",
        "id_company__name",
        "id_role__name",
    )
    ordering = (
        "email",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            "Personal",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                )
            },
        ),
        (
            "Company Access",
            {
                "fields": (
                    "id_company",
                    "id_role",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Django Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "last_login",
                    "created_at",
                )
            },
        ),
    )

    readonly_fields = (
        "last_login",
        "created_at",
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": (
                    "wide",
                ),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "id_company",
                    "id_role",
                    "status",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )