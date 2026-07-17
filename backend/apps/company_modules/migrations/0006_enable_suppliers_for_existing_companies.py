# Generated manually for Suppliers module visibility in company module control.

from django.db import migrations


def enable_suppliers_for_existing_companies(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    CompanyModule = apps.get_model("company_modules", "CompanyModule")

    for company in Company.objects.all().iterator():
        CompanyModule.objects.update_or_create(
            id_company=company,
            module="suppliers",
            defaults={"is_enabled": True},
        )


def disable_seeded_suppliers(apps, schema_editor):
    CompanyModule = apps.get_model("company_modules", "CompanyModule")
    CompanyModule.objects.filter(module="suppliers").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("company_modules", "0005_alter_companymodule_module"),
        ("companies", "0006_remove_company_website"),
    ]

    operations = [
        migrations.RunPython(enable_suppliers_for_existing_companies, migrations.RunPython.noop),
    ]
