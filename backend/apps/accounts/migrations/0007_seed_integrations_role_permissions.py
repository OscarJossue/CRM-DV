from django.db import migrations


def seed_integrations_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_terms = ("admin", "administrator", "super", "owner", "ceo")

    for role in Role.objects.all():
        role_name = (role.name or "").lower()
        is_admin = any(term in role_name for term in admin_terms)
        RolePermission.objects.get_or_create(
            id_role=role,
            module="integrations",
            defaults={
                "can_view": is_admin,
                "can_create": is_admin,
                "can_edit": is_admin,
                "can_delete": is_admin,
                "can_approve": is_admin,
            },
        )


def unseed_integrations_permissions(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    RolePermission.objects.filter(module="integrations").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_seed_suppliers_role_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_integrations_permissions, unseed_integrations_permissions),
    ]
