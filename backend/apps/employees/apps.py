from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.employees"
    label = "employees"
    verbose_name = "Employee Profiles"

    def ready(self):
        from . import signals  # noqa: F401
