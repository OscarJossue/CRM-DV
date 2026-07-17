from apps.core.permissions import user_has_module_permission

MODULE_SUPPLIERS = "suppliers"


def user_can_access_supplier(user, supplier):
    if not user or not user.is_authenticated or not supplier:
        return False

    if user.is_superuser:
        return True

    return supplier.id_company_id == user.id_company_id


def user_can_access_supplier_object(user, obj):
    if not user or not user.is_authenticated or not obj:
        return False

    if user.is_superuser:
        return True

    return obj.id_company_id == user.id_company_id


def user_can_manage_suppliers(user, permission_field="can_view"):
    return user_has_module_permission(user, MODULE_SUPPLIERS, permission_field)
