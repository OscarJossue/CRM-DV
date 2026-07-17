from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_useraccount_is_company_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="preferred_language",
            field=models.CharField(
                choices=[("en", "English"), ("es", "Español")],
                default="en",
                help_text="Personal interface language used by platform administrators.",
                max_length=10,
            ),
        ),
    ]
