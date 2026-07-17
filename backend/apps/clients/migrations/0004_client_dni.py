from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0003_client_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="dni",
            field=models.CharField(
                blank=True,
                help_text="Optional tax or identity document number.",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="client",
            index=models.Index(
                fields=["id_company", "dni"],
                name="client_company_dni_idx",
            ),
        ),
    ]
