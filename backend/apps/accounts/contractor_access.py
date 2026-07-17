"""Helpers for the restricted contractor workspace."""


def user_is_contractor_only(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_company_owner", False):
        return False
    role = getattr(user, "id_role", None)
    return bool(role and getattr(role, "is_contractor_only", False))
