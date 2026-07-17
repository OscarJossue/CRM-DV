from .models import Invoice


def invoice_list_for_user(user):
    queryset = Invoice.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_estimate",
    ).prefetch_related("items").all().order_by(
        "-issue_date",
        "-id_invoice",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def invoice_get_for_user(user, id_invoice):
    return invoice_list_for_user(user).filter(
        id_invoice=id_invoice,
    ).first()


def list_invoices(company=None):
    queryset = Invoice.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_estimate",
    ).prefetch_related("items").all().order_by(
        "-issue_date",
        "-id_invoice",
    )

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_invoices_by_id(pk):
    return Invoice.objects.filter(pk=pk).first()