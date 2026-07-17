import calendar
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.core.ui_translation import translate_ui_text as ui
from apps.platform_documents.models import PlatformDocument
from apps.platform_notifications.models import PlatformNotificationLog
from apps.platform_payments.models import PlatformPayment
from apps.platform_subscriptions.models import PlatformSubscription

from .models import PlatformCalendarEvent
from .models.choices import (
    EVENT_PRIORITY_HIGH,
    EVENT_PRIORITY_NORMAL,
    EVENT_TYPE_RENEWAL,
)


PLATFORM_CALENDAR_EVENT_TYPES = [
    ("manual", "Manual Events"),
    ("renewal", "Renewals"),
    ("payment", "Payments"),
    ("document", "Documents"),
    ("notification", "Notifications"),
    ("company", "Company Status"),
]


def normalize_month(year=None, month=None):
    today = timezone.localdate()

    try:
        year = int(year or today.year)
    except (TypeError, ValueError):
        year = today.year

    try:
        month = int(month or today.month)
    except (TypeError, ValueError):
        month = today.month

    if month < 1 or month > 12:
        month = today.month

    return year, month


def get_month_bounds(year=None, month=None):
    year, month = normalize_month(year, month)

    first_day = date(year, month, 1)
    last_day_number = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_number)

    return first_day, last_day


def get_month_navigation(year, month):
    year, month = normalize_month(year, month)

    current = date(year, month, 1)
    previous_month_date = current - timedelta(days=1)

    if month == 12:
        next_month_date = date(year + 1, 1, 1)
    else:
        next_month_date = date(year, month + 1, 1)

    return {
        "previous_year": previous_month_date.year,
        "previous_month": previous_month_date.month,
        "next_year": next_month_date.year,
        "next_month": next_month_date.month,
    }


def as_date(value):
    if not value:
        return None

    if hasattr(value, "date") and callable(value.date):
        return value.date()

    return value


def as_time(value):
    if not value:
        return None

    if hasattr(value, "time") and callable(value.time):
        return value.time()

    return None


def format_days_left(days_left):
    from django.utils.translation import get_language

    language = (get_language() or "en").lower()
    if language.startswith("es"):
        unit = "día restante" if days_left == 1 else "días restantes"
    else:
        unit = "day left" if days_left == 1 else "days left"
    return f"{days_left} {unit}"


def make_item(
    *,
    source,
    event_type,
    event_type_label,
    title,
    item_date,
    item_time=None,
    status="",
    status_label="",
    priority=EVENT_PRIORITY_NORMAL,
    company=None,
    subscription=None,
    description="",
    url="#",
    meta="",
):
    return {
        "source": source,
        "event_type": event_type,
        "event_type_label": event_type_label,
        "title": title,
        "date": item_date,
        "time": item_time,
        "status": status,
        "status_label": status_label or status,
        "priority": priority,
        "priority_label": ui("High") if priority == EVENT_PRIORITY_HIGH else ui("Normal"),
        "company": company,
        "subscription": subscription,
        "description": description,
        "url": url,
        "meta": meta,
    }


def build_subscription_renewal_items(start_date, end_date):
    subscriptions = (
        PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        )
        .filter(
            renewal_date__gte=start_date,
            renewal_date__lte=end_date,
        )
        .order_by("renewal_date")
    )

    items = []
    today = timezone.localdate()

    for subscription in subscriptions:
        if not subscription.renewal_date:
            continue

        days_left = (subscription.renewal_date - today).days
        priority = EVENT_PRIORITY_HIGH if days_left <= 7 else EVENT_PRIORITY_NORMAL

        company_name = subscription.id_company.name if subscription.id_company else ui("Unknown Company")
        plan_name = subscription.id_plan.name if subscription.id_plan else ui("No Plan")

        items.append(
            make_item(
                source="subscription",
                event_type="renewal",
                event_type_label=ui("Renewal"),
                title=f"{ui('Renewal')}: {company_name}",
                item_date=subscription.renewal_date,
                status=subscription.status,
                status_label=subscription.get_status_display(),
                priority=priority,
                company=subscription.id_company,
                subscription=subscription,
                description=f"{ui('Plan')}: {plan_name}. {ui('Review renewal, payment status and company access.')}",
                url=reverse(
                    "platform_subscriptions:detail",
                    kwargs={"id_subscription": subscription.id_subscription},
                ),
                meta=format_days_left(days_left) if days_left >= 0 else ui("Overdue"),
            )
        )

    return items


def build_manual_event_items(start_date, end_date):
    events = (
        PlatformCalendarEvent.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        )
        .filter(
            start_date__gte=start_date,
            start_date__lte=end_date,
        )
        .order_by("start_date", "start_time", "title")
    )

    items = []

    for event in events:
        items.append(
            make_item(
                source="manual",
                event_type="manual",
                event_type_label=event.get_event_type_display(),
                title=event.title,
                item_date=event.start_date,
                item_time=event.start_time,
                status=event.status,
                status_label=event.get_status_display(),
                priority=event.priority,
                company=event.id_company,
                subscription=event.id_subscription,
                description=event.description or "",
                url=reverse(
                    "platform_calendar:detail",
                    kwargs={"id_event": event.id_event},
                ),
                meta=event.id_company.name if event.id_company else ui("Internal event"),
            )
        )

    return items


def build_payment_items(start_date, end_date):
    payments = (
        PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_document",
            "received_by",
        )
        .filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date,
        )
        .order_by("payment_date", "payment_number")
    )

    items = []

    for payment in payments:
        priority = EVENT_PRIORITY_HIGH if payment.status in ["pending", "failed"] else EVENT_PRIORITY_NORMAL

        items.append(
            make_item(
                source="payment",
                event_type="payment",
                event_type_label=ui("SaaS Payment"),
                title=f"{ui('Payment')}: {payment.payment_number}",
                item_date=payment.payment_date,
                status=payment.status,
                status_label=payment.get_status_display(),
                priority=priority,
                company=payment.id_company,
                subscription=payment.id_subscription,
                description=payment.notes or payment.reference or "",
                url=reverse(
                    "platform_payments:detail",
                    kwargs={"id_payment": payment.id_payment},
                ),
                meta=f"${payment.amount}",
            )
        )

    return items


def build_document_items(start_date, end_date):
    documents = (
        PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        )
        .filter(
            Q(issue_date__gte=start_date, issue_date__lte=end_date)
            | Q(due_date__gte=start_date, due_date__lte=end_date)
        )
        .order_by("issue_date", "due_date", "document_number")
    )

    items = []
    today = timezone.localdate()

    for document in documents:
        if document.issue_date and start_date <= document.issue_date <= end_date:
            items.append(
                make_item(
                    source="document",
                    event_type="document",
                    event_type_label=document.get_document_type_display(),
                    title=f"{ui('Issued')}: {document.document_number}",
                    item_date=document.issue_date,
                    status=document.status,
                    status_label=document.get_status_display(),
                    priority=EVENT_PRIORITY_NORMAL,
                    company=document.id_company,
                    subscription=document.id_subscription,
                    description=document.notes or document.terms or "",
                    url=reverse(
                        "platform_documents:detail",
                        kwargs={"id_document": document.id_document},
                    ),
                    meta=f"${document.total}",
                )
            )

        if document.due_date and start_date <= document.due_date <= end_date:
            priority = EVENT_PRIORITY_HIGH if document.due_date <= today and document.status != "paid" else EVENT_PRIORITY_NORMAL

            items.append(
                make_item(
                    source="document",
                    event_type="document",
                    event_type_label=ui("Document Due"),
                    title=f"{ui('Due')}: {document.document_number}",
                    item_date=document.due_date,
                    status=document.status,
                    status_label=document.get_status_display(),
                    priority=priority,
                    company=document.id_company,
                    subscription=document.id_subscription,
                    description=document.notes or document.terms or "",
                    url=reverse(
                        "platform_documents:detail",
                        kwargs={"id_document": document.id_document},
                    ),
                    meta=f"${document.total}",
                )
            )

    return items


def build_notification_items(start_date, end_date):
    notifications = (
        PlatformNotificationLog.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        )
        .filter(
            Q(scheduled_at__date__gte=start_date, scheduled_at__date__lte=end_date)
            | Q(sent_at__date__gte=start_date, sent_at__date__lte=end_date)
            | Q(created_at__date__gte=start_date, created_at__date__lte=end_date)
        )
        .order_by("scheduled_at", "sent_at", "created_at")
    )

    items = []

    for notification in notifications:
        source_dt = notification.scheduled_at or notification.sent_at or notification.created_at
        notification_date = as_date(source_dt)

        if not notification_date:
            continue

        priority = EVENT_PRIORITY_HIGH if notification.status in ["pending", "failed"] else EVENT_PRIORITY_NORMAL

        items.append(
            make_item(
                source="notification",
                event_type="notification",
                event_type_label=notification.get_notification_type_display(),
                title=notification.subject or ui("Platform Notification"),
                item_date=notification_date,
                item_time=as_time(source_dt),
                status=notification.status,
                status_label=notification.get_status_display(),
                priority=priority,
                company=notification.id_company,
                subscription=notification.id_subscription,
                description=notification.message or notification.error_message or "",
                url=reverse(
                    "platform_notifications:detail",
                    kwargs={"id_notification": notification.id_notification},
                ),
                meta=notification.recipient_email,
            )
        )

    return items


def build_company_status_items(start_date, end_date):
    companies = (
        Company.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        .order_by("created_at", "name")
    )

    items = []

    for company in companies:
        company_date = as_date(company.created_at)

        if not company_date:
            continue

        priority = EVENT_PRIORITY_HIGH if company.status != "active" else EVENT_PRIORITY_NORMAL

        items.append(
            make_item(
                source="company",
                event_type="company",
                event_type_label=ui("Company Created"),
                title=f"{ui('Company')}: {company.name}",
                item_date=company_date,
                item_time=as_time(company.created_at),
                status=company.status,
                status_label=company.get_status_display(),
                priority=priority,
                company=company,
                description=company.description or company.email or "",
                url=reverse(
                    "companies:company_detail",
                    kwargs={"id_company": company.id_company},
                ),
                meta=f"/{company.slug}/dashboard/",
            )
        )

    inactive_companies = Company.objects.filter(status="inactive").order_by("name")

    if start_date <= timezone.localdate() <= end_date:
        for company in inactive_companies:
            items.append(
                make_item(
                    source="company",
                    event_type="company",
                    event_type_label=ui("Company Inactive"),
                    title=f"{ui('Inactive company')}: {company.name}",
                    item_date=timezone.localdate(),
                    status=company.status,
                    status_label=company.get_status_display(),
                    priority=EVENT_PRIORITY_HIGH,
                    company=company,
                    description=ui("This company is currently inactive. Review access, subscription and payment status."),
                    url=reverse(
                        "companies:company_detail",
                        kwargs={"id_company": company.id_company},
                    ),
                    meta=f"/{company.slug}/dashboard/",
                )
            )

    return items


def item_matches_search(item, q):
    if not q:
        return True

    q_lower = q.lower().strip()

    company = item.get("company")
    company_name = company.name if company else ""

    searchable = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("meta") or ""),
            str(item.get("event_type_label") or ""),
            str(item.get("status_label") or ""),
            str(company_name or ""),
        ]
    ).lower()

    return q_lower in searchable


def get_platform_calendar_items(start_date, end_date, event_type=None, q=None):
    items = []

    items.extend(build_manual_event_items(start_date, end_date))
    items.extend(build_subscription_renewal_items(start_date, end_date))
    items.extend(build_payment_items(start_date, end_date))
    items.extend(build_document_items(start_date, end_date))
    items.extend(build_notification_items(start_date, end_date))
    items.extend(build_company_status_items(start_date, end_date))

    if event_type:
        items = [
            item
            for item in items
            if item.get("event_type") == event_type
        ]

    if q:
        items = [
            item
            for item in items
            if item_matches_search(item, q)
        ]

    return sorted(
        [
            item
            for item in items
            if item.get("date")
        ],
        key=lambda item: (
            item.get("date") or timezone.localdate(),
            item.get("time") or datetime.min.time(),
            item.get("title") or "",
        ),
    )


def group_calendar_items_by_day(items):
    grouped = {}

    for item in items:
        item_date = item.get("date")

        if not item_date:
            continue

        grouped.setdefault(item_date, [])
        grouped[item_date].append(item)

    return grouped


def build_month_calendar_weeks(year, month, grouped_items):
    today = timezone.localdate()
    year, month = normalize_month(year, month)

    month_calendar = calendar.Calendar(firstweekday=6)
    weeks = []

    for week in month_calendar.monthdatescalendar(year, month):
        week_days = []

        for day_date in week:
            day_items = grouped_items.get(day_date, [])

            week_days.append(
                {
                    "date": day_date,
                    "day_number": day_date.day,
                    "is_today": day_date == today,
                    "is_current_month": day_date.month == month,
                    "items": day_items,
                    "item_count": len(day_items),
                    "visible_items": day_items[:4],
                    "hidden_count": max(len(day_items) - 4, 0),
                }
            )

        weeks.append(week_days)

    return weeks