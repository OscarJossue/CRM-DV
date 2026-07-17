from .models import Inspection


def inspection_list_for_user(user):
    queryset = Inspection.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_inspector",
    ).all().order_by("-inspection_date", "-created_at")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    if not user.id_company_id:
        return queryset.none()

    return queryset.filter(
        id_project__id_company_id=user.id_company_id,
    )


def inspection_get_for_user(user, id_inspection):
    return inspection_list_for_user(user).filter(
        id_inspection=id_inspection,
    ).first()


def inspection_list_for_project(user, project):
    queryset = inspection_list_for_user(user)

    return queryset.filter(
        id_project=project,
    )