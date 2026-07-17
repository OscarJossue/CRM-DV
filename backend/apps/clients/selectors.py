from .models import Client


def client_list_for_user(user):
    queryset = Client.objects.select_related("id_company").all().order_by(
        "name",
        "client_code",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    if not user.id_company_id:
        return queryset.none()

    return queryset.filter(id_company_id=user.id_company_id)


def client_get_for_user(user, id_client):
    return client_list_for_user(user).filter(
        id_client=id_client,
    ).first()


def list_clients(company=None):
    queryset = Client.objects.select_related("id_company").all().order_by(
        "name",
        "client_code",
    )

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_clients_by_id(pk):
    return Client.objects.select_related("id_company").filter(
        pk=pk,
    ).first()