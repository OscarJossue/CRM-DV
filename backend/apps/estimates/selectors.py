from .models import Estimate


def estimate_list_for_user(user):
    queryset = Estimate.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_inspection_assignment",
    ).all().order_by(
        "-issue_date",
        "-id_estimate",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def estimate_get_for_user(user, id_estimate):
    return estimate_list_for_user(user).filter(
        id_estimate=id_estimate,
    ).first()


def list_estimates(company=None):
    queryset = Estimate.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_inspection_assignment",
    ).all().order_by(
        "-issue_date",
        "-id_estimate",
    )

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_estimates_by_id(pk):
    return Estimate.objects.filter(pk=pk).first()
