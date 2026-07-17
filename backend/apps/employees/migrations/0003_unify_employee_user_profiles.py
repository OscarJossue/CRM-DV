import django.utils.timezone
from django.db import migrations


def unify_employee_profiles(apps, schema_editor):
    UserAccount = apps.get_model("accounts", "UserAccount")
    Employee = apps.get_model("employees", "Employee")

    for user in UserAccount.objects.all().iterator():
        hire_date = (
            user.created_at.date()
            if user.created_at
            else django.utils.timezone.localdate()
        )
        employee, created = Employee.objects.get_or_create(
            id_user_id=user.id_user,
            defaults={
                "id_company_id": user.id_company_id,
                "status": user.status,
                "hire_date": hire_date,
            },
        )

        changed = []
        if employee.id_company_id != user.id_company_id:
            employee.id_company_id = user.id_company_id
            changed.append("id_company")
        if employee.status != user.status:
            employee.status = user.status
            changed.append("status")
        if not employee.hire_date:
            employee.hire_date = hire_date
            changed.append("hire_date")
        if not employee.position and employee.category:
            employee.position = employee.category
            changed.append("position")

        if changed and not created:
            employee.save(update_fields=changed)


def reverse_profile_unification(apps, schema_editor):
    # Profiles are preserved on rollback to avoid deleting historical data.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_unify_employee_user_permissions"),
        ("employees", "0002_alter_employee_options_alter_employee_hourly_rate_and_more"),
    ]

    operations = [
        migrations.RunPython(
            unify_employee_profiles,
            reverse_code=reverse_profile_unification,
        ),
    ]
