import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_unify_employee_user_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="useraccount",
            name="id_company",
            field=models.ForeignKey(
                blank=True,
                db_column="id_company",
                help_text="Required for tenant users; empty for platform staff and superusers.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_accounts",
                to="companies.company",
            ),
        ),
    ]
