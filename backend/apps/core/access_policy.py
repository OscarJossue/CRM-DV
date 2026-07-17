"""Central runtime access policy for CRM users.

The platform has two independent controls:

* the user account status;
* the company status chosen by the platform administrator.

Subscription synchronization is intentionally *not* performed from this module.
A page request or login attempt must never mutate the company record. Subscription
updates, reactivations and the explicit synchronization management command remain
responsible for changing company.status.
"""

from apps.accounts.models.choices import STATUS_ACTIVE as USER_STATUS_ACTIVE
from apps.companies.models.choices import STATUS_ACTIVE as COMPANY_STATUS_ACTIVE

from .tenant import user_can_access_crm_admin


ACCESS_ALLOWED = "allowed"
ACCESS_USER_INACTIVE = "user_inactive"
ACCESS_USER_STATUS_INACTIVE = "user_status_inactive"
ACCESS_COMPANY_MISSING = "company_missing"
ACCESS_COMPANY_INACTIVE = "company_inactive"


def get_user_runtime_access_code(user):
    """Return the first runtime access failure code for *user*.

    Platform superusers/staff are intentionally independent from tenant company
    status, but their own account can still be disabled explicitly.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return ACCESS_USER_INACTIVE

    if not getattr(user, "is_active", False):
        return ACCESS_USER_INACTIVE

    if getattr(user, "status", USER_STATUS_ACTIVE) != USER_STATUS_ACTIVE:
        return ACCESS_USER_STATUS_INACTIVE

    if user_can_access_crm_admin(user):
        return ACCESS_ALLOWED

    company = getattr(user, "id_company", None)

    if not company:
        return ACCESS_COMPANY_MISSING

    if getattr(company, "status", COMPANY_STATUS_ACTIVE) != COMPANY_STATUS_ACTIVE:
        return ACCESS_COMPANY_INACTIVE

    return ACCESS_ALLOWED


def user_has_runtime_access(user):
    return get_user_runtime_access_code(user) == ACCESS_ALLOWED


def company_is_runtime_active(company):
    return bool(
        company
        and getattr(company, "status", COMPANY_STATUS_ACTIVE) == COMPANY_STATUS_ACTIVE
    )
