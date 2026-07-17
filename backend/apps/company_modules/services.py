from django.db import transaction

from apps.accounts.models.choices import TENANT_MODULE_CHOICES

from .models import CompanyModule


@transaction.atomic
def sync_company_modules(company, default_enabled=True):
    created_items = []

    for module_value, module_label in TENANT_MODULE_CHOICES:
        company_module, created = CompanyModule.objects.get_or_create(
            id_company=company,
            module=module_value,
            defaults={
                "is_enabled": default_enabled,
            },
        )

        if created:
            created_items.append(company_module)

    return created_items


@transaction.atomic
def set_company_module_status(company, module, is_enabled):
    company_module, created = CompanyModule.objects.update_or_create(
        id_company=company,
        module=module,
        defaults={
            "is_enabled": is_enabled,
        },
    )

    return company_module


@transaction.atomic
def bulk_update_company_modules(company, enabled_modules):
    sync_company_modules(company, default_enabled=False)

    for module_value, module_label in TENANT_MODULE_CHOICES:
        CompanyModule.objects.update_or_create(
            id_company=company,
            module=module_value,
            defaults={
                "is_enabled": module_value in enabled_modules,
            },
        )

    return CompanyModule.objects.filter(id_company=company)


def create_company_modules(**data):
    return CompanyModule.objects.create(**data)


def update_company_modules(instance, **data):
    for field, value in data.items():
        setattr(instance, field, value)

    instance.full_clean()
    instance.save()

    return instance
