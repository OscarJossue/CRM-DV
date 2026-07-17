from .models import CompanyModule


ALWAYS_ENABLED_MODULES = {
    "dashboard",
    "companies",
    "users",
    "roles",
    "company_modules",
}


def company_module_list_for_user(user):
    queryset = CompanyModule.objects.select_related(
        "id_company",
    ).all().order_by(
        "id_company__name",
        "module",
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def company_module_get_for_user(user, id_company_module):
    return company_module_list_for_user(user).filter(
        id_company_module=id_company_module,
    ).first()


def company_has_module_enabled(company, module):
    if not module:
        return True

    if module in ALWAYS_ENABLED_MODULES:
        return True

    if not company:
        return True

    company_modules_exist = CompanyModule.objects.filter(
        id_company=company,
    ).exists()

    if not company_modules_exist:
        return True

    return CompanyModule.objects.filter(
        id_company=company,
        module=module,
        is_enabled=True,
    ).exists()


def enabled_modules_for_company(company):
    return CompanyModule.objects.filter(
        id_company=company,
        is_enabled=True,
    ).values_list("module", flat=True)


def list_company_modules(company=None):
    queryset = CompanyModule.objects.select_related(
        "id_company",
    ).all().order_by(
        "id_company__name",
        "module",
    )

    if company:
        queryset = queryset.filter(id_company=company)

    return queryset


def get_company_modules_by_id(pk):
    return CompanyModule.objects.filter(pk=pk).first()
