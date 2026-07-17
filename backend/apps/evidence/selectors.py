from .models import EvidenceFile


def evidence_file_list_for_user(user):
    queryset = EvidenceFile.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_user",
    ).all().order_by("-created_at")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_project__id_company=user.id_company_id)


def evidence_file_get_for_user(user, id_file):
    return evidence_file_list_for_user(user).filter(id_file=id_file).first()


def list_evidence(company=None):
    queryset = EvidenceFile.objects.select_related(
        "id_project",
        "id_project__id_company",
        "id_project__id_client",
        "id_user",
    ).all().order_by("-created_at")

    if company:
        queryset = queryset.filter(id_project__id_company=company)

    return queryset


def get_evidence_by_id(pk):
    return EvidenceFile.objects.filter(pk=pk).first()
