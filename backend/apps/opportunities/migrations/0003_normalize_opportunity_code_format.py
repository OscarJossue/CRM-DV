from django.db import migrations


def normalize_opportunity_codes(apps, schema_editor):
    Lead = apps.get_model("opportunities", "Lead")
    for opportunity in Lead.objects.all().only("id_lead", "opportunity_code").iterator():
        expected = f"OPP-{opportunity.id_lead:06d}"
        if opportunity.opportunity_code != expected:
            Lead.objects.filter(id_lead=opportunity.id_lead).update(opportunity_code=expected)


def reverse_opportunity_codes(apps, schema_editor):
    Lead = apps.get_model("opportunities", "Lead")
    for opportunity in Lead.objects.all().only("id_lead", "opportunity_code").iterator():
        previous = f"O_{opportunity.id_lead:05d}"
        if opportunity.opportunity_code != previous:
            Lead.objects.filter(id_lead=opportunity.id_lead).update(opportunity_code=previous)


class Migration(migrations.Migration):
    dependencies = [("opportunities", "0002_alter_lead_source_alter_lead_status")]

    operations = [
        migrations.RunPython(normalize_opportunity_codes, reverse_opportunity_codes),
    ]
