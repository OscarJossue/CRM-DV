from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.accounts.models.choices import STATUS_ACTIVE

from .models import Notification
from .models.choices import (
    NOTIFICATION_STATUS_ARCHIVED,
    NOTIFICATION_STATUS_READ,
    NOTIFICATION_STATUS_UNREAD,
    NOTIFICATION_TYPE_BILLING,
)


@transaction.atomic
def notification_create(*, id_user, title, message=None, type=None, status=NOTIFICATION_STATUS_UNREAD):
    return Notification.objects.create(
        id_user=id_user,
        title=title,
        message=message,
        type=type,
        status=status or NOTIFICATION_STATUS_UNREAD,
    )


@transaction.atomic
def notification_create_once(
    *,
    id_user,
    title,
    message=None,
    type=None,
    status=NOTIFICATION_STATUS_UNREAD,
):
    existing_notification = Notification.objects.filter(
        id_user=id_user,
        title=title,
        message=message,
        type=type,
    ).first()

    if existing_notification:
        return existing_notification, False

    notification = Notification.objects.create(
        id_user=id_user,
        title=title,
        message=message,
        type=type,
        status=status or NOTIFICATION_STATUS_UNREAD,
    )

    return notification, True


@transaction.atomic
def notification_update(notification, **data):
    allowed_fields = [
        "id_user",
        "type",
        "title",
        "message",
        "status",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(notification, field, data[field])

    notification.save()
    return notification


@transaction.atomic
def notification_mark_read(notification):
    notification.status = NOTIFICATION_STATUS_READ
    notification.save(update_fields=["status"])
    return notification


@transaction.atomic
def notification_mark_unread(notification):
    notification.status = NOTIFICATION_STATUS_UNREAD
    notification.save(update_fields=["status"])
    return notification


@transaction.atomic
def notification_archive(notification):
    notification.status = NOTIFICATION_STATUS_ARCHIVED
    notification.save(update_fields=["status"])
    return notification


@transaction.atomic
def mark_all_user_notifications_read(user):
    if not user or not user.is_authenticated:
        return 0

    updated_count = Notification.objects.filter(
        id_user=user,
        status=NOTIFICATION_STATUS_UNREAD,
    ).update(status=NOTIFICATION_STATUS_READ)

    return updated_count


def get_user_notifications(user, limit=None, include_archived=False):
    if not user or not user.is_authenticated:
        return Notification.objects.none()

    queryset = Notification.objects.filter(id_user=user).order_by("-created_at")

    if not include_archived:
        queryset = queryset.exclude(status=NOTIFICATION_STATUS_ARCHIVED)

    if limit:
        return queryset[:limit]

    return queryset


def get_user_unread_notifications(user, limit=3):
    if not user or not user.is_authenticated:
        return Notification.objects.none()

    return Notification.objects.filter(
        id_user=user,
        status=NOTIFICATION_STATUS_UNREAD,
    ).order_by("-created_at")[:limit]


def get_user_unread_notification_count(user):
    if not user or not user.is_authenticated:
        return 0

    return Notification.objects.filter(
        id_user=user,
        status=NOTIFICATION_STATUS_UNREAD,
    ).count()


def get_company_notification_users(company):
    if not company:
        return UserAccount.objects.none()

    return (
        UserAccount.objects.select_related("id_company", "id_role")
        .filter(
            id_company=company,
            is_active=True,
            status=STATUS_ACTIVE,
        )
        .order_by("id_role__name", "first_name", "email")
    )


def notify_company_users(*, company, title, message, type=NOTIFICATION_TYPE_BILLING):
    users = get_company_notification_users(company)

    created_count = 0
    skipped_count = 0
    notifications = []

    for user in users:
        notification, created = notification_create_once(
            id_user=user,
            title=title,
            message=message,
            type=type,
            status=NOTIFICATION_STATUS_UNREAD,
        )

        notifications.append(notification)

        if created:
            created_count += 1
        else:
            skipped_count += 1

    return {
        "created": created_count,
        "skipped": skipped_count,
        "notifications": notifications,
    }


def notify_subscription_renewal_reminder(subscription):
    if not subscription or not subscription.id_company:
        return {
            "created": 0,
            "skipped": 0,
            "notifications": [],
        }

    company = subscription.id_company
    plan_name = subscription.id_plan.name if subscription.id_plan else "Current plan"
    renewal_date = subscription.renewal_date.strftime("%Y-%m-%d") if subscription.renewal_date else "Not defined"

    title = "Your CRM plan is close to renewal"

    message = (
        f"Your CRM subscription is close to its renewal date. "
        f"Company: {company.name}. "
        f"Plan: {plan_name}. "
        f"Renewal date: {renewal_date}. "
        f"Please contact CEO Marketing to confirm your payment and avoid service interruption."
    )

    return notify_company_users(
        company=company,
        title=title,
        message=message,
        type=NOTIFICATION_TYPE_BILLING,
    )


def notify_subscription_expired(subscription):
    if not subscription or not subscription.id_company:
        return {
            "created": 0,
            "skipped": 0,
            "notifications": [],
        }

    company = subscription.id_company
    plan_name = subscription.id_plan.name if subscription.id_plan else "Current plan"
    renewal_date = subscription.renewal_date.strftime("%Y-%m-%d") if subscription.renewal_date else "Not defined"

    title = "Your CRM plan has expired"

    message = (
        f"Your CRM subscription appears to be expired. "
        f"Company: {company.name}. "
        f"Plan: {plan_name}. "
        f"Renewal date: {renewal_date}. "
        f"Your CRM workspace may be limited until the renewal payment is confirmed."
    )

    return notify_company_users(
        company=company,
        title=title,
        message=message,
        type=NOTIFICATION_TYPE_BILLING,
    )


def notify_payment_registered(payment):
    if not payment or not payment.id_company:
        return {
            "created": 0,
            "skipped": 0,
            "notifications": [],
        }

    company = payment.id_company
    payment_date = payment.payment_date or timezone.localdate()
    payment_date_text = payment_date.strftime("%Y-%m-%d")
    amount = payment.amount or 0

    title = "Payment received for your CRM plan"

    message = (
        f"We received a CRM payment for your company. "
        f"Company: {company.name}. "
        f"Payment number: {payment.payment_number}. "
        f"Amount: ${amount}. "
        f"Payment date: {payment_date_text}. "
        f"Your CRM access will remain active according to your subscription renewal status."
    )

    return notify_company_users(
        company=company,
        title=title,
        message=message,
        type=NOTIFICATION_TYPE_BILLING,
    )

    @transaction.atomic
    def mark_all_user_notifications_read(user):
        if not user or not user.is_authenticated:
            return 0

        updated_count = Notification.objects.filter(
            id_user=user,
            status=NOTIFICATION_STATUS_UNREAD,
        ).update(status=NOTIFICATION_STATUS_READ)

        return updated_count