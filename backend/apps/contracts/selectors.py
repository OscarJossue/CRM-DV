from django.db.models import Q

from .models import Contract


def contract_base_queryset():
    return Contract.objects.select_related(
        "id_company",
        "id_client",
        "id_client__id_company",
        "id_project",
        "id_project__id_company",
        "created_by",
        "updated_by",
        "sent_by",
        "voided_by",
    )


def contract_list_for_user(user):
    queryset = contract_base_queryset().all().order_by("-id_contract")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(
        Q(id_company_id=user.id_company_id)
        | Q(id_company__isnull=True, id_project__id_company_id=user.id_company_id)
    ).distinct()


def contract_get_for_user(user, id_contract):
    return contract_list_for_user(user).filter(
        id_contract=id_contract,
    ).first()


def list_contracts(company=None):
    queryset = contract_base_queryset().all().order_by("-id_contract")

    if company:
        queryset = queryset.filter(
            Q(id_company=company)
            | Q(id_company__isnull=True, id_project__id_company=company)
        ).distinct()

    return queryset


def get_contracts_by_id(pk):
    return Contract.objects.filter(pk=pk).first()