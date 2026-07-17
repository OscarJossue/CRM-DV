from .models import Lead


def lead_list_for_user(user):
    queryset = Lead.objects.select_related(
        "id_company",
        "id_assigned_user",
        "id_converted_client",
    ).all().order_by("-created_at")

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def lead_get_for_user(user, id_lead):
    return lead_list_for_user(user).filter(id_lead=id_lead).first()


def list_leads(company=None):
    queryset = Lead.objects.select_related(
        "id_company",
        "id_assigned_user",
        "id_converted_client",
    ).all().order_by("-created_at")

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_leads_by_id(pk):
    return Lead.objects.filter(pk=pk).first()
