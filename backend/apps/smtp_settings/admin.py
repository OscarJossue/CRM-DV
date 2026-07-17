from django.contrib import admin

from .models import SmtpSetting


@admin.register(SmtpSetting)
class SmtpSettingAdmin(admin.ModelAdmin):
    list_display = (
        "id_smtp_setting",
        "id_company",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "default_from_email",
        "is_active",
        "last_test_status",
        "last_tested_at",
    )

    list_filter = (
        "is_active",
        "use_tls",
        "use_ssl",
        "last_test_status",
    )

    search_fields = (
        "id_company__name",
        "smtp_username",
        "default_from_email",
        "from_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_tested_at",
        "last_test_status",
        "last_test_message",
    )