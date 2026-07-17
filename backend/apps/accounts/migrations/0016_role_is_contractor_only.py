from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_alter_rolepermission_module"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="is_contractor_only",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Restricts users in this role to assigned inspections/projects, "
                    "evidence uploads, notes and submit-for-audit actions."
                ),
            ),
        ),
    ]
