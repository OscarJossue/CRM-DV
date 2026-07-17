# Generated manually for Suppliers role visibility.

from django.db import migrations


def seed_suppliers_role_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    for role in Role.objects.all().iterator():
        role_name = (role.name or "").lower()
        is_admin_role = "admin" in role_name or "administrador" in role_name or "super" in role_name

        RolePermission.objects.get_or_create(
            id_role=role,
            module="suppliers",
            defaults={
                "can_view": is_admin_role,
                "can_create": is_admin_role,
                "can_edit": is_admin_role,
                "can_delete": is_admin_role,
                "can_approve": is_admin_role,
            },
        )


def unseed_suppliers_role_permissions(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    RolePermission.objects.filter(module="suppliers").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_rolepermission_module"),
    ]

    operations = [
        migrations.RunPython(seed_suppliers_role_permissions, migrations.RunPython.noop),
    ]
