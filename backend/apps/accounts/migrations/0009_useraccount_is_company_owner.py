from django.db import migrations, models


def mark_existing_company_owners(apps, schema_editor):
    UserAccount = apps.get_model("accounts", "UserAccount")
    UserAccount.objects.filter(id_role__name__iexact="Owner").update(
        is_company_owner=True
    )


def unmark_existing_company_owners(apps, schema_editor):
    UserAccount = apps.get_model("accounts", "UserAccount")
    UserAccount.objects.filter(is_company_owner=True).update(
        is_company_owner=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_alter_rolepermission_module"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="is_company_owner",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Allows this user to manage company-level workspace settings.",
            ),
        ),
        migrations.RunPython(
            mark_existing_company_owners,
            reverse_code=unmark_existing_company_owners,
        ),
    ]
