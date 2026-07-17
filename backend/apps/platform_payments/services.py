import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.notifications.services import notify_payment_registered
from apps.platform_documents.models.choices import (
    DOCUMENT_STATUS_PAID,
    DOCUMENT_STATUS_SENT,
    DOCUMENT_STATUS_VOID,
)
from apps.platform_subscriptions.models import PlatformSubscription
from apps.platform_subscriptions.models.choices import (
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_CANCELED,
)
from apps.platform_subscriptions.services import sync_company_access, sync_subscription_status

from .models import PlatformPayment
from .models.choices import PAYMENT_STATUS_PAID


def generate_platform_payment_number():
    year = timezone.localdate().year

    last_payment = (
        PlatformPayment.objects.filter(
            payment_number__startswith=f"PAY-{year}-"
        )
        .order_by("-id_payment")
        .first()
    )

    if not last_payment:
        next_number = 1
    else:
        try:
            next_number = int(last_payment.payment_number.split("-")[-1]) + 1
        except Exception:
            next_number = last_payment.id_payment + 1

    return f"PAY-{year}-{next_number:05d}"


def get_document_paid_total(document):
    if not document:
        return Decimal("0.00")

    value = (
        PlatformPayment.objects.filter(
            id_document=document,
            status=PAYMENT_STATUS_PAID,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
    )

    return value or Decimal("0.00")


def get_document_balance(document):
    if not document:
        return Decimal("0.00")

    paid_total = get_document_paid_total(document)
    balance = Decimal(str(document.total or 0)) - paid_total

    if balance < 0:
        return Decimal("0.00")

    return balance


def sync_document_payment_status(document):
    if not document:
        return None

    if document.status == DOCUMENT_STATUS_VOID:
        return document

    paid_total = get_document_paid_total(document)
    document_total = Decimal(str(document.total or 0))

    if document_total > 0 and paid_total >= document_total:
        document.status = DOCUMENT_STATUS_PAID
        document.save(update_fields=["status", "updated_at"])
        return document

    if document.status == DOCUMENT_STATUS_PAID and paid_total < document_total:
        document.status = DOCUMENT_STATUS_SENT
        document.save(update_fields=["status", "updated_at"])
        return document

    return document


def add_months(original_date, months):
    month = original_date.month - 1 + months
    year = original_date.year + month // 12
    month = month % 12 + 1
    day = min(original_date.day, calendar.monthrange(year, month)[1])

    return date(year, month, day)


def get_plan_renewal_date(subscription, payment_date=None):
    today = payment_date or timezone.localdate()

    current_renewal_date = getattr(subscription, "renewal_date", None)

    if current_renewal_date and current_renewal_date >= today:
        base_date = current_renewal_date
    else:
        base_date = today

    plan = getattr(subscription, "id_plan", None)
    billing_cycle = str(getattr(plan, "billing_cycle", "") or "").lower()

    if "year" in billing_cycle or "annual" in billing_cycle:
        return add_months(base_date, 12)

    if "quarter" in billing_cycle:
        return add_months(base_date, 3)

    if "semi" in billing_cycle or "six" in billing_cycle:
        return add_months(base_date, 6)

    if "week" in billing_cycle:
        return base_date + timedelta(days=7)

    return add_months(base_date, 1)


def get_latest_company_subscription(company):
    if not company:
        return None

    return (
        PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        )
        .filter(id_company=company)
        .order_by("-created_at")
        .first()
    )


def attach_default_subscription_if_missing(payment):
    if not payment:
        return None

    if payment.id_subscription_id:
        return payment.id_subscription

    subscription = get_latest_company_subscription(payment.id_company)

    if not subscription:
        return None

    payment.id_subscription = subscription

    if payment.pk:
        payment.save(update_fields=["id_subscription", "updated_at"])

    return subscription


def activate_subscription_from_paid_payment(payment):
    if not payment:
        return None

    if payment.status != PAYMENT_STATUS_PAID:
        return None

    subscription = attach_default_subscription_if_missing(payment)

    if not subscription:
        return None

    if subscription.status == SUBSCRIPTION_CANCELED:
        return subscription

    today = payment.payment_date or timezone.localdate()

    update_fields = []

    if not subscription.start_date:
        subscription.start_date = today
        update_fields.append("start_date")

    subscription.renewal_date = get_plan_renewal_date(
        subscription,
        payment_date=today,
    )
    update_fields.append("renewal_date")

    subscription.status = SUBSCRIPTION_ACTIVE
    update_fields.append("status")

    subscription.end_date = None
    update_fields.append("end_date")

    subscription.save(update_fields=update_fields)

    sync_subscription_status(subscription)
    subscription.refresh_from_db()

    if payment.id_company:
        sync_company_access(payment.id_company)

    return subscription


def apply_payment_effects(payment):
    if not payment:
        return payment

    if payment.status == PAYMENT_STATUS_PAID and not payment.payment_date:
        payment.payment_date = timezone.localdate()
        payment.save(update_fields=["payment_date", "updated_at"])

    if payment.status == PAYMENT_STATUS_PAID:
        activate_subscription_from_paid_payment(payment)

        try:
            notify_payment_registered(payment)
        except Exception:
            pass

    if payment.id_document:
        sync_document_payment_status(payment.id_document)

    return payment