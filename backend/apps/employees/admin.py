from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id_employee", "id_user", "id_company", "position", "hire_date", "status",
    )
    search_fields = (
        "id_user__first_name", "id_user__last_name", "id_user__email",
        "id_company__name", "identification", "position",
    )
    list_filter = ("status", "id_company")
    readonly_fields = ("hire_date",)
    ordering = ("id_user__first_name", "id_user__last_name")
