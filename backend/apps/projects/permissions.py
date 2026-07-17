
from apps.core.permissions import HasModulePermission


class ProjectPermission(HasModulePermission):
    pass


def _get_user_role_name(user):
    role = getattr(user, "role", None)

    if not role:
        role = getattr(user, "id_role", None)

    if not role:
        return ""

    return (
        getattr(role, "name", "")
        or getattr(role, "role_name", "")
        or str(role)
    ).strip().lower()


def _user_has_project_access_role(user):
    role_name = _get_user_role_name(user)

    access_keywords = [
        "owner",
        "admin",
        "administrator",
        "secretary",
        "manager",
        "supervisor",
        "inspector",
        "view",
        "viewer",
    ]

    return any(
        keyword in role_name
        for keyword in access_keywords
    )


def user_can_access_project(user, project):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if not getattr(user, "id_company_id", None):
        return False

    if project.id_company_id != user.id_company_id:
        return False

    if _user_has_project_access_role(user):
        return True

    if project.id_inspector_id == user.id:
        return True

    from apps.projects.models import ProjectAssignment

    return ProjectAssignment.objects.filter(
        id_project=project,
        id_user=user,
    ).exists()


def user_can_access_project_assignment(user, assignment):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if not getattr(user, "id_company_id", None):
        return False

    if assignment.id_project.id_company_id != user.id_company_id:
        return False

    if _user_has_project_access_role(user):
        return True

    if assignment.id_user_id == user.id:
        return True

    if assignment.id_project.id_inspector_id == user.id:
        return True

    return False
