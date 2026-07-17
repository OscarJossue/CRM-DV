from django.apps import AppConfig


class SmtpSettingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.smtp_settings"
    label = "smtp_settings"
    verbose_name = "SMTP Settings"
    