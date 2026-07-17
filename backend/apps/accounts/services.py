from django.db import transaction

from .models import RolePermission
from .models.choices import STATUS_ACTIVE, STATUS_INACTIVE


def _post_checked(post_data, field_name):
    return post_data.get(field_name) == "on"


@transaction.atomic
def sync_role_permissions_from_post(role, allowed_modules, post_data):
    allowed_modules = list(allowed_modules)

    if getattr(role, "is_contractor_only", False):
        contractor_modules = {"inspections", "projects"}
        RolePermission.objects.filter(id_role=role).delete()
        for module_value in contractor_modules.intersection(allowed_modules):
            RolePermission.objects.create(
                id_role=role,
                module=module_value,
                can_view=True,
                can_create=False,
                can_edit=False,
                can_delete=False,
                can_approve=False,
            )
        return role

    for module_value in allowed_modules:
        can_view = _post_checked(post_data, f"{module_value}_can_view")
        can_manage = _post_checked(post_data, f"{module_value}_can_manage")
        can_approve = _post_checked(post_data, f"{module_value}_can_approve")

        legacy_can_create = _post_checked(post_data, f"{module_value}_can_create")
        legacy_can_edit = _post_checked(post_data, f"{module_value}_can_edit")
        legacy_can_delete = _post_checked(post_data, f"{module_value}_can_delete")

        if legacy_can_create or legacy_can_edit or legacy_can_delete:
            can_manage = True

        if can_manage or can_approve:
            can_view = True

        RolePermission.objects.update_or_create(
            id_role=role,
            module=module_value,
            defaults={
                "can_view": can_view,
                "can_create": can_manage,
                "can_edit": can_manage,
                "can_delete": can_manage,
                "can_approve": can_approve,
            },
        )

    RolePermission.objects.filter(
        id_role=role,
    ).exclude(
        module__in=allowed_modules,
    ).delete()

    return role


@transaction.atomic
def user_account_activate(user_account):
    user_account.status = STATUS_ACTIVE
    user_account.is_active = True
    user_account.full_clean()
    user_account.save(
        update_fields=[
            "status",
            "is_active",
        ]
    )
    from apps.employees.services import sync_employee_profile
    sync_employee_profile(user_account)

    return user_account


@transaction.atomic
def user_account_deactivate(user_account):
    user_account.status = STATUS_INACTIVE
    user_account.is_active = False
    user_account.full_clean()
    user_account.save(
        update_fields=[
            "status",
            "is_active",
        ]
    )

    return user_account