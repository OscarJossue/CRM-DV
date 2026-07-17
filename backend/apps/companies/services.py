from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.models.choices import STATUS_ACTIVE, TENANT_MODULE_CODES
from apps.company_modules.models import CompanyModule
from apps.platform_subscriptions.models import PlatformSubscription
from apps.platform_subscriptions.models.choices import SUBSCRIPTION_ACTIVE
from apps.platform_subscriptions.services import (
    calculate_plan_renewal_date,
    sync_company_access,
)

from .models import Company
from .models.choices import PLAN_STARTER, STATUS_ACTIVE as COMPANY_ACTIVE, STATUS_INACTIVE


def get_tenant_module_codes():
    """Return the canonical company-workspace module codes."""
    return list(TENANT_MODULE_CODES)


def get_unique_module_codes():
    """Backward-compatible name used by older maintenance code."""
    return get_tenant_module_codes()


def get_company_plan_code_from_platform_plan(platform_plan):
    if not platform_plan:
        return PLAN_STARTER

    plan_code = getattr(platform_plan, "code", "") or ""
    valid_company_plan_codes = [
        value for value, _label in Company._meta.get_field("plan").choices
    ]
    return plan_code if plan_code in valid_company_plan_codes else PLAN_STARTER


def sync_company_limits_from_platform_plan(company, platform_plan):
    if not company or not platform_plan:
        return company

    next_plan = get_company_plan_code_from_platform_plan(platform_plan)
    next_user_limit = getattr(platform_plan, "max_users", None) or 1
    update_fields = []

    if company.plan != next_plan:
        company.plan = next_plan
        update_fields.append("plan")
    if company.user_limit != next_user_limit:
        company.user_limit = next_user_limit
        update_fields.append("user_limit")
    if update_fields:
        company.save(update_fields=update_fields)

    return company


def create_owner_role_for_company(company):
    """Create/repair the tenant administrator role with tenant-only access."""
    role, _created = Role.objects.get_or_create(
        id_company=company,
        name="Owner",
        defaults={
            "description": "Company administrator with full access inside this company workspace.",
            "status": STATUS_ACTIVE,
        },
    )

    role.description = "Company administrator with full access inside this company workspace."
    role.status = STATUS_ACTIVE
    role.save(update_fields=["description", "status"])

    tenant_modules = get_tenant_module_codes()

    # Remove stale platform/global rows left by previous provisioning logic.
    RolePermission.objects.filter(id_role=role).exclude(module__in=tenant_modules).delete()

    for module_code in tenant_modules:
        RolePermission.objects.update_or_create(
            id_role=role,
            module=module_code,
            defaults={
                "can_view": True,
                "can_create": True,
                "can_edit": True,
                "can_delete": True,
                "can_approve": True,
            },
        )

    return role


def enable_default_company_modules(company):
    """Enable all company modules, never platform administration modules."""
    tenant_modules = get_tenant_module_codes()

    CompanyModule.objects.filter(id_company=company).exclude(module__in=tenant_modules).delete()

    for module_code in tenant_modules:
        CompanyModule.objects.update_or_create(
            id_company=company,
            module=module_code,
            defaults={"is_enabled": True},
        )


def company_activate(company):
    company.status = COMPANY_ACTIVE
    company.save(update_fields=["status"])
    return company


def company_deactivate(company):
    company.status = STATUS_INACTIVE
    company.save(update_fields=["status"])
    return company


@transaction.atomic
def provision_company_with_admin(*, company_data, admin_data, subscription_data):
    """Create company, administrator, permissions and subscription atomically.

    Passwords are passed only to Django's create_user()/set_password pipeline;
    plaintext values are never stored in Company, audit metadata or messages.
    """
    platform_plan = subscription_data.get("id_plan")
    start_date = subscription_data.get("start_date") or timezone.localdate()
    renewal_date = subscription_data.get("renewal_date")

    if not renewal_date:
        renewal_date = calculate_plan_renewal_date(platform_plan, start_date=start_date)

    company = Company.objects.create(
        name=company_data.get("name"),
        legal_name=company_data.get("legal_name"),
        email=company_data.get("email"),
        phone=company_data.get("phone"),
        address=company_data.get("address"),
        city=company_data.get("city"),
        state=company_data.get("state"),
        country=company_data.get("country"),
        logo=company_data.get("logo"),
        description=company_data.get("description"),
        plan=get_company_plan_code_from_platform_plan(platform_plan),
        user_limit=getattr(platform_plan, "max_users", None) or 1,
        status=COMPANY_ACTIVE,
    )

    owner_role = create_owner_role_for_company(company)
    enable_default_company_modules(company)

    administrator = UserAccount.objects.create_user(
        email=(admin_data.get("email") or "").strip().lower(),
        password=admin_data.get("password"),
        id_company=company,
        id_role=owner_role,
        first_name=admin_data.get("first_name"),
        last_name=admin_data.get("last_name"),
        phone=admin_data.get("phone"),
        status=STATUS_ACTIVE,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        is_company_owner=True,
    )

    subscription = PlatformSubscription.objects.create(
        id_company=company,
        id_plan=platform_plan,
        status=SUBSCRIPTION_ACTIVE,
        start_date=start_date,
        renewal_date=renewal_date,
        notes=None,
    )

    sync_company_limits_from_platform_plan(company, platform_plan)
    sync_company_access(company)
    company.refresh_from_db()

    if company.status != COMPANY_ACTIVE:
        # This should only occur with inconsistent plan dates. Rolling back is
        # safer than leaving a newly created administrator unable to log in.
        raise ValueError("The new company could not be activated. Review the subscription dates.")

    return {
        "company": company,
        "administrator": administrator,
        "owner_user": administrator,  # compatibility for older callers
        "owner_role": owner_role,
        "subscription": subscription,
    }
