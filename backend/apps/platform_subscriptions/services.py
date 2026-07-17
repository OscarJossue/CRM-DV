from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.companies.models.choices import STATUS_ACTIVE, STATUS_INACTIVE
from apps.notifications.services import notify_subscription_expired
from apps.platform_plans.models.choices import (
    BILLING_CUSTOM,
    BILLING_MONTHLY,
    BILLING_YEARLY,
    CUSTOM_CYCLE_DAYS,
    CUSTOM_CYCLE_MONTHS,
    CUSTOM_CYCLE_WEEKS,
    CUSTOM_CYCLE_YEARS,
)

from .models import PlatformSubscription


SUBSCRIPTION_STATUS_TRIAL = "trial"
SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_EXPIRED = "expired"
SUBSCRIPTION_STATUS_SUSPENDED = "suspended"
SUBSCRIPTION_STATUS_CANCELED = "canceled"

CURRENT_SUBSCRIPTION_STATUSES = [
    SUBSCRIPTION_STATUS_TRIAL,
    SUBSCRIPTION_STATUS_ACTIVE,
]

BLOCKED_SUBSCRIPTION_STATUSES = [
    SUBSCRIPTION_STATUS_EXPIRED,
    SUBSCRIPTION_STATUS_SUSPENDED,
    SUBSCRIPTION_STATUS_CANCELED,
]


def calculate_plan_renewal_date(plan, start_date=None):
    start_date = start_date or timezone.localdate()

    if not plan:
        return start_date + relativedelta(months=1)

    if plan.billing_cycle == BILLING_YEARLY:
        return start_date + relativedelta(years=1)

    if plan.billing_cycle == BILLING_MONTHLY:
        return start_date + relativedelta(months=1)

    if plan.billing_cycle == BILLING_CUSTOM:
        count = plan.custom_cycle_count or 1
        unit = plan.custom_cycle_unit

        if unit == CUSTOM_CYCLE_DAYS:
            return start_date + relativedelta(days=count)

        if unit == CUSTOM_CYCLE_WEEKS:
            return start_date + relativedelta(weeks=count)

        if unit == CUSTOM_CYCLE_MONTHS:
            return start_date + relativedelta(months=count)

        if unit == CUSTOM_CYCLE_YEARS:
            return start_date + relativedelta(years=count)

    return start_date + relativedelta(months=1)


def subscription_is_date_current(subscription, today=None):
    if not subscription:
        return False

    today = today or timezone.localdate()

    if subscription.status not in CURRENT_SUBSCRIPTION_STATUSES:
        return False

    if subscription.renewal_date and subscription.renewal_date < today:
        return False

    if subscription.end_date and subscription.end_date < today:
        return False

    return True


def sync_subscription_status(subscription, today=None):
    if not subscription:
        return None

    today = today or timezone.localdate()

    if not subscription.renewal_date and subscription.id_plan_id:
        subscription.renewal_date = calculate_plan_renewal_date(
            subscription.id_plan,
            start_date=subscription.start_date or today,
        )
        subscription.save(update_fields=["renewal_date"])

    if subscription.status in [
        SUBSCRIPTION_STATUS_SUSPENDED,
        SUBSCRIPTION_STATUS_CANCELED,
    ]:
        return subscription

    is_expired_by_renewal = bool(
        subscription.renewal_date and subscription.renewal_date < today
    )

    is_expired_by_end_date = bool(
        subscription.end_date and subscription.end_date < today
    )

    if is_expired_by_renewal or is_expired_by_end_date:
        if subscription.status != SUBSCRIPTION_STATUS_EXPIRED:
            subscription.status = SUBSCRIPTION_STATUS_EXPIRED
            subscription.save(update_fields=["status"])

            try:
                notify_subscription_expired(subscription)
            except Exception:
                pass

        return subscription

    if subscription.status == SUBSCRIPTION_STATUS_EXPIRED:
        subscription.status = SUBSCRIPTION_STATUS_ACTIVE
        subscription.save(update_fields=["status"])

    return subscription


def company_has_current_subscription(company, today=None):
    if not company:
        return False

    today = today or timezone.localdate()

    subscriptions = PlatformSubscription.objects.filter(id_company=company)

    for subscription in subscriptions:
        sync_subscription_status(subscription, today=today)

    return subscriptions.filter(
        status__in=CURRENT_SUBSCRIPTION_STATUSES,
    ).filter(
        renewal_date__gte=today,
    ).exists()


def sync_company_access(company, today=None):
    if not company:
        return None

    today = today or timezone.localdate()

    has_access = company_has_current_subscription(company, today=today)

    next_status = STATUS_ACTIVE if has_access else STATUS_INACTIVE

    if company.status != next_status:
        company.status = next_status
        company.save(update_fields=["status"])

    return company


def reactivate_platform_subscription(subscription, *, today=None, force_new_cycle=True):
    """Reactivate a subscription and make sure company access becomes valid again.

    The old implementation only changed status to active and then immediately
    synced the subscription. When renewal_date was in the past, sync converted
    it back to expired, so the company never really reactivated.
    """
    if not subscription:
        return None

    today = today or timezone.localdate()

    if not subscription.start_date:
        subscription.start_date = today

    should_refresh_renewal = (
        force_new_cycle
        or not subscription.renewal_date
        or subscription.renewal_date < today
    )

    if should_refresh_renewal:
        subscription.renewal_date = calculate_plan_renewal_date(
            subscription.id_plan,
            start_date=today,
        )

    # Reactivation reopens the account; end date belongs only to closed subscriptions.
    subscription.end_date = None

    subscription.status = SUBSCRIPTION_STATUS_ACTIVE
    subscription.save(
        update_fields=[
            "status",
            "start_date",
            "renewal_date",
            "end_date",
        ]
    )

    sync_company_access(subscription.id_company, today=today)

    return subscription


def sync_all_platform_subscriptions(today=None):
    today = today or timezone.localdate()

    subscriptions = PlatformSubscription.objects.select_related(
        "id_company",
        "id_plan",
    ).all()

    touched_company_ids = set()

    for subscription in subscriptions:
        sync_subscription_status(subscription, today=today)

        if subscription.id_company_id:
            touched_company_ids.add(subscription.id_company_id)

    Company = PlatformSubscription._meta.get_field("id_company").remote_field.model

    for company in Company.objects.filter(id_company__in=touched_company_ids):
        sync_company_access(company, today=today)

    return {
        "subscriptions_checked": subscriptions.count(),
        "companies_checked": len(touched_company_ids),
    }