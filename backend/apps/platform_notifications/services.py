from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.notifications.services import (
    notify_subscription_expired,
    notify_subscription_renewal_reminder,
)
from apps.platform_email.services import send_platform_email
from apps.platform_subscriptions.models import PlatformSubscription
from apps.platform_subscriptions.models.choices import (
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_EXPIRED,
    SUBSCRIPTION_TRIAL,
)

from .models import PlatformNotificationLog
from .models.choices import (
    NOTIFICATION_CHANNEL_EMAIL,
    NOTIFICATION_STATUS_FAILED,
    NOTIFICATION_STATUS_SENT,
    NOTIFICATION_TYPE_RENEWAL_REMINDER,
    NOTIFICATION_TYPE_SUBSCRIPTION_EXPIRED,
)


def get_company_owner_email(company):
    owner = (
        UserAccount.objects.filter(
            id_company=company,
            id_role__name__iexact="Owner",
            is_active=True,
        )
        .order_by("id_user")
        .first()
    )

    if owner and owner.email:
        return owner.email

    if company.email:
        return company.email

    return None


def build_renewal_subject(company, subscription):
    return f"CRM subscription renewal reminder - {company.name}"


def build_renewal_message(company, subscription):
    plan_name = subscription.id_plan.name if subscription.id_plan else "Current plan"
    renewal_date = subscription.renewal_date.strftime("%Y-%m-%d") if subscription.renewal_date else "Not defined"

    return (
        f"Hello {company.name},\n\n"
        f"This is a reminder that your CEO Marketing CRM subscription is close to renewal.\n\n"
        f"Company: {company.name}\n"
        f"Plan: {plan_name}\n"
        f"Renewal Date: {renewal_date}\n\n"
        f"Please contact CEO Marketing to confirm your renewal and avoid service interruption.\n\n"
        f"Thank you,\n"
        f"CEO Marketing CRM"
    )


def build_expired_subject(company, subscription):
    return f"CRM subscription expired - {company.name}"


def build_expired_message(company, subscription):
    plan_name = subscription.id_plan.name if subscription.id_plan else "Current plan"
    renewal_date = subscription.renewal_date.strftime("%Y-%m-%d") if subscription.renewal_date else "Not defined"

    return (
        f"Hello {company.name},\n\n"
        f"Your CEO Marketing CRM subscription appears to be expired.\n\n"
        f"Company: {company.name}\n"
        f"Plan: {plan_name}\n"
        f"Renewal Date: {renewal_date}\n\n"
        f"Your CRM workspace may be limited until the renewal payment is confirmed.\n\n"
        f"Thank you,\n"
        f"CEO Marketing CRM"
    )


def notification_already_sent_today(company, subscription, notification_type):
    today = timezone.localdate()

    return PlatformNotificationLog.objects.filter(
        id_company=company,
        id_subscription=subscription,
        notification_type=notification_type,
        status=NOTIFICATION_STATUS_SENT,
        created_at__date=today,
    ).exists()


def create_notification_log(
    *,
    company,
    subscription,
    notification_type,
    recipient_email,
    subject,
    message,
    created_by=None,
):
    return PlatformNotificationLog.objects.create(
        id_company=company,
        id_subscription=subscription,
        notification_type=notification_type,
        channel=NOTIFICATION_CHANNEL_EMAIL,
        recipient_email=recipient_email,
        subject=subject,
        message=message,
        status="pending",
        scheduled_at=timezone.now(),
        created_by=created_by,
    )


def send_platform_notification(notification):
    try:
        email_log = send_platform_email(
            recipient_email=notification.recipient_email,
            subject=notification.subject,
            message=notification.message,
            company=notification.id_company,
            email_type=notification.notification_type,
        )

        if email_log.status == "sent":
            notification.status = NOTIFICATION_STATUS_SENT
            notification.sent_at = timezone.now()
            notification.error_message = ""
            notification.save(update_fields=["status", "sent_at", "error_message"])
        else:
            notification.status = NOTIFICATION_STATUS_FAILED
            notification.error_message = email_log.error_message or "Email was not sent."
            notification.save(update_fields=["status", "error_message"])

    except Exception as error:
        notification.status = NOTIFICATION_STATUS_FAILED
        notification.error_message = str(error)
        notification.save(update_fields=["status", "error_message"])

    return notification


def send_renewal_reminder(subscription, created_by=None, force=False):
    company = subscription.id_company

    if not company:
        return None

    recipient_email = get_company_owner_email(company)

    if not recipient_email:
        return None

    if not force and notification_already_sent_today(
        company,
        subscription,
        NOTIFICATION_TYPE_RENEWAL_REMINDER,
    ):
        return None

    subject = build_renewal_subject(company, subscription)
    message = build_renewal_message(company, subscription)

    notification = create_notification_log(
        company=company,
        subscription=subscription,
        notification_type=NOTIFICATION_TYPE_RENEWAL_REMINDER,
        recipient_email=recipient_email,
        subject=subject,
        message=message,
        created_by=created_by,
    )

    return send_platform_notification(notification)


def send_expired_subscription_notice(subscription, created_by=None, force=False):
    company = subscription.id_company

    if not company:
        return None

    recipient_email = get_company_owner_email(company)

    if not recipient_email:
        return None

    if not force and notification_already_sent_today(
        company,
        subscription,
        NOTIFICATION_TYPE_SUBSCRIPTION_EXPIRED,
    ):
        return None

    subject = build_expired_subject(company, subscription)
    message = build_expired_message(company, subscription)

    notification = create_notification_log(
        company=company,
        subscription=subscription,
        notification_type=NOTIFICATION_TYPE_SUBSCRIPTION_EXPIRED,
        recipient_email=recipient_email,
        subject=subject,
        message=message,
        created_by=created_by,
    )

    return send_platform_notification(notification)


def send_due_subscription_notifications(days_before=5, created_by=None, force=False):
    today = timezone.localdate()
    target_date = today + timedelta(days=int(days_before))

    renewal_subscriptions = (
        PlatformSubscription.objects.select_related("id_company", "id_plan")
        .filter(
            status__in=[SUBSCRIPTION_ACTIVE, SUBSCRIPTION_TRIAL],
            renewal_date__gte=today,
            renewal_date__lte=target_date,
        )
        .order_by("renewal_date")
    )

    expired_subscriptions = (
        PlatformSubscription.objects.select_related("id_company", "id_plan")
        .filter(
            status=SUBSCRIPTION_EXPIRED,
        )
        .order_by("renewal_date")
    )

    sent = 0
    skipped = 0
    failed = 0
    bell_created = 0
    bell_skipped = 0

    for subscription in renewal_subscriptions:
        try:
            bell_result = notify_subscription_renewal_reminder(subscription)
            bell_created += bell_result.get("created", 0)
            bell_skipped += bell_result.get("skipped", 0)
        except Exception:
            pass

        notification = send_renewal_reminder(
            subscription,
            created_by=created_by,
            force=force,
        )

        if not notification:
            skipped += 1
        elif notification.status == NOTIFICATION_STATUS_SENT:
            sent += 1
        else:
            failed += 1

    for subscription in expired_subscriptions:
        try:
            bell_result = notify_subscription_expired(subscription)
            bell_created += bell_result.get("created", 0)
            bell_skipped += bell_result.get("skipped", 0)
        except Exception:
            pass

        notification = send_expired_subscription_notice(
            subscription,
            created_by=created_by,
            force=force,
        )

        if not notification:
            skipped += 1
        elif notification.status == NOTIFICATION_STATUS_SENT:
            sent += 1
        else:
            failed += 1

    return {
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "days_before": days_before,
        "bell_created": bell_created,
        "bell_skipped": bell_skipped,
    }