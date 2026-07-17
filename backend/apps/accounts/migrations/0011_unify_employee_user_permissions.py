from django.db import migrations


def merge_employee_permissions_into_users(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")

    employee_permissions = list(
        RolePermission.objects.filter(module="employees").order_by("id_role_id")
    )
    for employee_permission in employee_permissions:
        user_permission, _ = RolePermission.objects.get_or_create(
            id_role_id=employee_permission.id_role_id,
            module="users",
        )
        changed = []
        for field in (
            "can_view",
            "can_create",
            "can_edit",
            "can_delete",
            "can_approve",
        ):
            merged = bool(
                getattr(user_permission, field) or getattr(employee_permission, field)
            )
            if getattr(user_permission, field) != merged:
                setattr(user_permission, field, merged)
                changed.append(field)
        if changed:
            user_permission.save(update_fields=changed)

    RolePermission.objects.filter(module="employees").delete()


def restore_legacy_employee_permissions(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    for user_permission in RolePermission.objects.filter(module="users"):
        RolePermission.objects.get_or_create(
            id_role_id=user_permission.id_role_id,
            module="employees",
            defaults={
                "can_view": user_permission.can_view,
                "can_create": user_permission.can_create,
                "can_edit": user_permission.can_edit,
                "can_delete": user_permission.can_delete,
                "can_approve": user_permission.can_approve,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_useraccount_preferred_language"),
    ]

    operations = [
        migrations.RunPython(
            merge_employee_permissions_into_users,
            reverse_code=restore_legacy_employee_permissions,
        ),
    ]
