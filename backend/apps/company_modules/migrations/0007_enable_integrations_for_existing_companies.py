from django.db import migrations


def enable_integrations(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    CompanyModule = apps.get_model("company_modules", "CompanyModule")

    for company in Company.objects.all():
        CompanyModule.objects.get_or_create(
            id_company=company,
            module="integrations",
            defaults={"is_enabled": True},
        )


def disable_integrations(apps, schema_editor):
    CompanyModule = apps.get_model("company_modules", "CompanyModule")
    CompanyModule.objects.filter(module="integrations").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("company_modules", "0006_enable_suppliers_for_existing_companies"),
    ]

    operations = [
        migrations.RunPython(enable_integrations, disable_integrations),
    ]
