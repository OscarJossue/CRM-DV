import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0003_unify_employee_user_profiles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="category",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=100,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="employee",
            name="hire_date",
            field=models.DateField(
                default=django.utils.timezone.localdate,
                editable=False,
            ),
        ),
    ]
