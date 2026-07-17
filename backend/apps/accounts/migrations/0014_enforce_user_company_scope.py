from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_detach_platform_users_from_companies"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="useraccount",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(is_staff=True, id_company__isnull=True)
                    | models.Q(
                        is_staff=False,
                        is_superuser=False,
                        id_company__isnull=False,
                    )
                ),
                name="user_company_scope_ck",
            ),
        ),
    ]
