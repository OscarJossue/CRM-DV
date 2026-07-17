from django.db import migrations


def merge_employee_module_into_users(apps, schema_editor):
    CompanyModule = apps.get_model("company_modules", "CompanyModule")

    for employee_module in CompanyModule.objects.filter(module="employees"):
        user_module, _ = CompanyModule.objects.get_or_create(
            id_company_id=employee_module.id_company_id,
            module="users",
            defaults={"is_enabled": employee_module.is_enabled},
        )
        if employee_module.is_enabled and not user_module.is_enabled:
            user_module.is_enabled = True
            user_module.save(update_fields=["is_enabled"])

    CompanyModule.objects.filter(module="employees").delete()


def restore_employee_module(apps, schema_editor):
    CompanyModule = apps.get_model("company_modules", "CompanyModule")
    for user_module in CompanyModule.objects.filter(module="users"):
        CompanyModule.objects.get_or_create(
            id_company_id=user_module.id_company_id,
            module="employees",
            defaults={"is_enabled": user_module.is_enabled},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_unify_employee_user_permissions"),
        ("company_modules", "0008_alter_companymodule_module"),
    ]

    operations = [
        migrations.RunPython(
            merge_employee_module_into_users,
            reverse_code=restore_employee_module,
        ),
    ]
