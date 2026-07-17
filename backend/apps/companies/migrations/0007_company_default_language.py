from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0006_remove_company_website"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="default_language",
            field=models.CharField(
                choices=[("en", "English"), ("es", "Español")],
                db_index=True,
                default="en",
                help_text="Default interface language for this company workspace.",
                max_length=10,
            ),
        ),
    ]
