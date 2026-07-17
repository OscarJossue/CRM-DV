from apps.accounts.models.choices import TENANT_MODULE_CODES
from apps.companies.models.choices import (
    PLAN_BUSINESS,
    PLAN_INTERNAL,
    PLAN_PRO,
    PLAN_STARTER,
)


ALL_MODULES = list(TENANT_MODULE_CODES)


PLAN_USER_LIMITS = {
    PLAN_INTERNAL: 50,
    PLAN_STARTER: 5,
    PLAN_PRO: 15,
    PLAN_BUSINESS: 30,
}


PLAN_MODULE_PRESETS = {
    PLAN_INTERNAL: ALL_MODULES,
    PLAN_STARTER: [
        "users",
        "roles",
        "notifications",
        "clients",
        "leads",
        "projects",
        "calendar_events",
    ],
    PLAN_PRO: [
        "users",
        "roles",
        "notifications",
        "clients",
        "leads",
        "projects",
        "calendar_events",
        "inspections",
        "evidence",
        "estimates",
        "invoices",
        "contracts",
        "reports",
    ],
    PLAN_BUSINESS: ALL_MODULES,
}


def get_modules_for_plan(plan):
    if not plan:
        return PLAN_MODULE_PRESETS.get(PLAN_STARTER, [])

    return PLAN_MODULE_PRESETS.get(plan, PLAN_MODULE_PRESETS.get(PLAN_STARTER, []))


def get_user_limit_for_plan(plan):
    if not plan:
        return PLAN_USER_LIMITS.get(PLAN_STARTER, 5)

    return PLAN_USER_LIMITS.get(plan, PLAN_USER_LIMITS.get(PLAN_STARTER, 5))


def module_is_enabled_for_plan(plan, module):
    return module in get_modules_for_plan(plan)