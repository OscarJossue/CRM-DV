from django.db import migrations
from django.db.models import Q


def detach_platform_users(apps, schema_editor):
    UserAccount = apps.get_model("accounts", "UserAccount")
    Employee = apps.get_model("employees", "Employee")

    platform_user_ids = list(
        UserAccount.objects.filter(Q(is_superuser=True) | Q(is_staff=True)).values_list(
            "id_user", flat=True
        )
    )

    if not platform_user_ids:
        return

    # Platform accounts are not employees of any tenant. Remove only their
    # compatibility profiles before clearing the tenant foreign keys.
    Employee.objects.filter(id_user_id__in=platform_user_ids).delete()
    UserAccount.objects.filter(id_user__in=platform_user_ids).update(
        id_company_id=None,
        id_role_id=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_allow_platform_users_without_company"),
        ("employees", "0004_finalize_unified_employee_fields"),
    ]

    operations = [
        migrations.RunPython(detach_platform_users, migrations.RunPython.noop),
    ]
