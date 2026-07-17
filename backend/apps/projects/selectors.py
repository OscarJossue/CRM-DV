from .models import Project, ProjectAssignment



def project_list_for_user(user):
    from django.db.models import Q

    from apps.accounts.contractor_access import user_is_contractor_only
    from apps.core.template_permissions import (
        PERMISSION_APPROVE,
        PERMISSION_EDIT,
        user_can_module_action,
    )

    queryset = Project.objects.select_related(
        "id_company",
        "id_client",
        "id_inspector",
        "id_opportunity",
    ).all().order_by("-created_at")

    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    if not getattr(user, "id_company_id", None):
        return queryset.none()

    queryset = queryset.filter(id_company_id=user.id_company_id)
    assigned_project_ids = ProjectAssignment.objects.filter(
        id_user=user,
        id_project__id_company_id=user.id_company_id,
    ).values_list("id_project_id", flat=True)

    # Contractor-only users are always restricted to their explicit field work.
    if user_is_contractor_only(user):
        return queryset.filter(
            Q(id_inspector=user) | Q(id_project__in=assigned_project_ids)
        ).distinct()

    # Company owners and users who manage/approve projects need the complete
    # company workspace. This avoids relying on role names such as "manager".
    if (
        getattr(user, "is_company_owner", False)
        or user_can_module_action(user, "projects", PERMISSION_EDIT)
        or user_can_module_action(user, "projects", PERMISSION_APPROVE)
    ):
        return queryset

    # View-only staff see only records explicitly assigned to them.
    return queryset.filter(
        Q(id_inspector=user) | Q(id_project__in=assigned_project_ids)
    ).distinct()



def project_get_for_user(user, id_project):
    return project_list_for_user(user).filter(
        id_project=id_project,
    ).first()


def assignment_list_for_user(user):
    queryset = ProjectAssignment.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_user",
        "id_user__id_role",
        "id_user__id_company",
    ).all().order_by("-assigned_at")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    if not user.id_company_id:
        return queryset.none()

    return queryset.filter(
        id_project__id_company_id=user.id_company_id,
    )