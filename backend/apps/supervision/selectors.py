from django.db.models import Q

from apps.core.template_permissions import PERMISSION_EDIT, user_can_module_action

from .models import Supervision


def _base_queryset():
    return Supervision.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_inspection_assignment",
        "id_inspection_assignment__client",
        "id_inspection_assignment__client__id_company",
        "id_inspection_assignment__inspector",
        "id_supervisor",
    ).order_by("-created_at")


def supervision_list_for_user(user):
    queryset = _base_queryset()

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    if not user.id_company_id:
        return queryset.none()

    queryset = queryset.filter(
        Q(id_project__id_company_id=user.id_company_id)
        | Q(id_inspection_assignment__client__id_company_id=user.id_company_id)
    )

    if getattr(user, "is_company_owner", False) or user_can_module_action(
        user, "supervision", PERMISSION_EDIT
    ):
        return queryset.distinct()

    return queryset.filter(id_supervisor=user).distinct()


def supervision_get_for_user(user, id_supervision):
    return supervision_list_for_user(user).filter(id_supervision=id_supervision).first()


def list_supervision(company=None):
    queryset = _base_queryset()
    if company:
        queryset = queryset.filter(
            Q(id_project__id_company=company)
            | Q(id_inspection_assignment__client__id_company=company)
        )
    return queryset.distinct()


def get_supervision_by_id(pk):
    return _base_queryset().filter(pk=pk).first()
