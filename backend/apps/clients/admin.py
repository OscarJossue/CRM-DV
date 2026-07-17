from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "id_client",
        "client_code",
        "name",
        "id_company",
        "dni",
        "phone",
        "email",
        "city",
        "state",
        "created_at",
    )

    search_fields = (
        "client_code",
        "name",
        "first_name",
        "middle_name",
        "last_name",
        "second_last_name",
        "dni",
        "phone",
        "email",
        "address",
        "city",
        "state",
        "id_company__name",
    )

    list_filter = (
        "id_company",
        "state",
        "city",
        "created_at",
    )

    readonly_fields = (
        "client_code",
        "created_at",
    )