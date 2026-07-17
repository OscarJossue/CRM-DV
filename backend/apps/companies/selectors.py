from .models import Company


def company_list_for_user(user):
    queryset = Company.objects.all().order_by("name")

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    company_id = getattr(user, "id_company_id", None)

    if not company_id:
        return queryset.none()

    return queryset.filter(id_company=company_id)


def company_get_by_id(id_company):
    return Company.objects.filter(id_company=id_company).first()


def company_get_for_user(user, id_company):
    queryset = company_list_for_user(user)
    return queryset.filter(id_company=id_company).first()


def company_active_list():
    return Company.objects.filter(status="active").order_by("name")
