from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from .translation_runtime import install_runtime_translation_adapters

        install_runtime_translation_adapters()
