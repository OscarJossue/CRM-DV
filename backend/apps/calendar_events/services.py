import calendar
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.permissions import user_has_module_permission
from apps.estimates.models import Estimate
from apps.inspections.models import Inspection, InspectionAssignment
from apps.invoices.models import Invoice
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.projects.models import Project

from .models import CalendarEvent
from .models.choices import EVENT_STATUS_CANCELLED, EVENT_STATUS_COMPLETED


CALENDAR_EVENT_TYPES = [
    ("manual", "Manual Events"),
    ("notification", "Notifications"),
    ("payment", "Payments"),
    ("invoice", "Invoices"),
    ("estimate", "Estimates"),
    ("project", "Projects"),
    ("inspection", "Inspections"),
]


@transaction.atomic
def calendar_event_create(**data):
    return CalendarEvent.objects.create(**data)


@transaction.atomic
def calendar_event_update(calendar_event, **data):
    allowed_fields = [
        "id_company",
        "related_type",
        "id_project",
        "id_inspection_assignment",
        "id_estimate",
        "id_invoice",
        "id_payment",
        "id_client",
        "id_opportunity",
        "id_assigned_user",
        "title",
        "description",
        "category",
        "priority",
        "event_date",
        "start_time",
        "end_time",
        "location",
        "status",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(calendar_event, field, data[field])

    calendar_event.full_clean()
    calendar_event.save()

    return calendar_event


@transaction.atomic
def calendar_event_complete(calendar_event):
    calendar_event.status = EVENT_STATUS_COMPLETED
    calendar_event.full_clean()
    calendar_event.save(update_fields=["status"])

    return calendar_event


@transaction.atomic
def calendar_event_cancel(calendar_event):
    calendar_event.status = EVENT_STATUS_CANCELLED
    calendar_event.full_clean()
    calendar_event.save(update_fields=["status"])

    return calendar_event


def create_calendar_events(**data):
    return calendar_event_create(**data)


def update_calendar_events(instance, **data):
    return calendar_event_update(instance, **data)


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


def company_url(company, path):
    clean_path = (path or "").lstrip("/")

    if company and getattr(company, "slug", None):
        return f"/{company.slug}/{clean_path}"

    return f"/{clean_path}"


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


def user_is_owner_or_admin(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    role = getattr(user, "id_role", None)
    role_name = (getattr(role, "name", "") or "").strip().lower()

    return "owner" in role_name or "admin" in role_name or "super" in role_name


def user_can_view_module(user, module_name):
    try:
        return user_has_module_permission(user, module_name, "can_view")
    except Exception:
        return False


def user_can_see_company_wide(user, module_name):
    return user_is_owner_or_admin(user) or user_can_view_module(user, module_name)


def user_project_filter(user):
    return (
        Q(id_inspector=user)
        | Q(assignments__id_user=user)
        | Q(created_by=user)
        | Q(updated_by=user)
    )


def user_related_project_ids(user, company):
    if not user or not company:
        return []

    return list(
        Project.objects.filter(
            id_company=company,
        )
        .filter(user_project_filter(user))
        .values_list("id_project", flat=True)
        .distinct()
    )


def make_item(
    *,
    source,
    event_type,
    event_type_label,
    title,
    item_date,
    item_time=None,
    end_time=None,
    status="",
    status_label="",
    priority="normal",
    company=None,
    description="",
    location="",
    assigned_to="",
    related_label="",
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
        "end_time": end_time,
        "status": status,
        "status_label": status_label or status,
        "priority": priority,
        "company": company,
        "description": description,
        "location": location,
        "assigned_to": assigned_to,
        "related_label": related_label,
        "url": url,
        "meta": meta,
    }


def build_manual_calendar_items(user, company, start_date, end_date):
    queryset = (
        CalendarEvent.objects.select_related(
            "id_company",
            "id_project",
            "id_assigned_user",
            "id_inspection_assignment",
            "id_inspection_assignment__client",
            "id_estimate",
            "id_estimate__id_client",
            "id_invoice",
            "id_invoice__id_client",
            "id_payment",
            "id_payment__id_client",
            "id_client",
            "id_opportunity",
            "id_opportunity__id_client",
        )
        .filter(
            id_company=company,
            event_date__gte=start_date,
            event_date__lte=end_date,
        )
        .order_by("event_date", "start_time", "title")
    )

    if not user_can_see_company_wide(user, "calendar_events"):
        queryset = queryset.filter(id_assigned_user=user)

    items = []

    for event in queryset:
        title = event.title or "Calendar Event"
        related_object = event.related_object
        related_label = str(related_object) if related_object else ""

        items.append(
            make_item(
                source="manual",
                event_type="manual",
                event_type_label=event.get_category_display(),
                title=title,
                item_date=event.event_date,
                item_time=event.start_time,
                end_time=event.end_time,
                status=event.status,
                status_label=event.get_status_display(),
                priority=event.priority,
                company=event.id_company,
                description=event.description or "",
                location=event.location or "",
                assigned_to=event.assigned_user_name,
                related_label=related_label,
                url=company_url(company, f"calendar/{event.id_event}/"),
                meta=related_label or event.assigned_user_name,
            )
        )

    return items


def build_notification_items(user, company, start_date, end_date):
    queryset = (
        Notification.objects.filter(
            id_user=user,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        .order_by("created_at")
    )

    items = []

    for notification in queryset:
        notification_date = as_date(notification.created_at)

        if not notification_date:
            continue

        priority = "high" if notification.status == "unread" else "normal"

        items.append(
            make_item(
                source="notification",
                event_type="notification",
                event_type_label="Notification",
                title=notification.title or "Notification",
                item_date=notification_date,
                item_time=as_time(notification.created_at),
                status=notification.status,
                status_label=notification.status,
                priority=priority,
                company=company,
                description=notification.message or "",
                url=company_url(company, f"notifications/{notification.id_notification}/"),
                meta=notification.type or "User notification",
            )
        )

    return items


def build_project_items(user, company, start_date, end_date):
    queryset = Project.objects.filter(id_company=company)

    if not user_can_see_company_wide(user, "projects"):
        queryset = queryset.filter(user_project_filter(user)).distinct()

    queryset = queryset.filter(
        Q(start_date__gte=start_date, start_date__lte=end_date)
        | Q(end_date__gte=start_date, end_date__lte=end_date)
    ).order_by("start_date", "end_date", "name")

    items = []

    for project in queryset:
        if project.start_date and start_date <= project.start_date <= end_date:
            items.append(
                make_item(
                    source="project",
                    event_type="project",
                    event_type_label="Project Start",
                    title=f"Start: {project.name}",
                    item_date=project.start_date,
                    status=project.status,
                    status_label=project.status,
                    priority="normal",
                    company=company,
                    description=project.project_address or project.description or "",
                    url=company_url(company, f"projects/{project.id_project}/"),
                    meta=project.project_code or "Project",
                )
            )

        if project.end_date and start_date <= project.end_date <= end_date:
            items.append(
                make_item(
                    source="project",
                    event_type="project",
                    event_type_label="Project End",
                    title=f"Due: {project.name}",
                    item_date=project.end_date,
                    status=project.status,
                    status_label=project.status,
                    priority="high" if project.status not in ["completed", "cancelled"] else "normal",
                    company=company,
                    description=project.project_address or project.description or "",
                    url=company_url(company, f"projects/{project.id_project}/"),
                    meta=project.project_code or "Project",
                )
            )

    return items


def build_inspection_items(user, company, start_date, end_date):
    items = []

    inspections = (
        Inspection.objects.select_related(
            "id_project",
            "id_project__id_company",
            "id_inspector",
        )
        .filter(
            id_project__id_company=company,
            inspection_date__date__gte=start_date,
            inspection_date__date__lte=end_date,
        )
        .order_by("inspection_date")
    )

    if not user_can_see_company_wide(user, "inspections"):
        inspections = inspections.filter(id_inspector=user)

    for inspection in inspections:
        inspection_date = as_date(inspection.inspection_date)

        if not inspection_date:
            continue

        items.append(
            make_item(
                source="inspection",
                event_type="inspection",
                event_type_label="Inspection",
                title=f"Inspection: {inspection.project_name}",
                item_date=inspection_date,
                item_time=as_time(inspection.inspection_date),
                status=inspection.status,
                status_label=inspection.get_status_display() if hasattr(inspection, "get_status_display") else inspection.status,
                priority="high" if inspection.status == "pending" else "normal",
                company=company,
                description=inspection.damage_description or "",
                url=company_url(company, f"inspections/legacy/{inspection.id_inspection}/"),
                meta=inspection.inspector_name if hasattr(inspection, "inspector_name") else "Inspector",
            )
        )

    assignments = (
        InspectionAssignment.objects.select_related(
            "client",
            "client__id_company",
            "inspector",
        )
        .filter(
            client__id_company=company,
            inspection_date__date__gte=start_date,
            inspection_date__date__lte=end_date,
        )
        .order_by("inspection_date")
    )

    if not user_can_see_company_wide(user, "inspections"):
        assignments = assignments.filter(inspector=user)

    for assignment in assignments:
        assignment_date = as_date(assignment.inspection_date)

        if not assignment_date:
            continue

        items.append(
            make_item(
                source="inspection",
                event_type="inspection",
                event_type_label="Inspection Assignment",
                title=f"Inspection Visit: {assignment.client_name}",
                item_date=assignment_date,
                item_time=as_time(assignment.inspection_date),
                status=assignment.status,
                status_label=assignment.get_status_display() if hasattr(assignment, "get_status_display") else assignment.status,
                priority="high" if assignment.status == "pending" else "normal",
                company=company,
                description=assignment.notes or assignment.inspection_notes or "",
                url=company_url(company, f"inspections/assignments/{assignment.id_assignment}/"),
                meta=assignment.inspector_name,
            )
        )

    return items


def build_estimate_items(user, company, start_date, end_date):
    queryset = Estimate.objects.select_related("id_project").filter(id_company=company)

    if not user_can_see_company_wide(user, "estimates"):
        related_project_ids = user_related_project_ids(user, company)

        queryset = queryset.filter(
            Q(created_by=user)
            | Q(updated_by=user)
            | Q(sent_by=user)
            | Q(id_project_id__in=related_project_ids)
        ).distinct()

    queryset = queryset.filter(
        Q(issue_date__gte=start_date, issue_date__lte=end_date)
        | Q(expiration_date__gte=start_date, expiration_date__lte=end_date)
    ).order_by("issue_date", "expiration_date")

    items = []

    for estimate in queryset:
        if estimate.issue_date and start_date <= estimate.issue_date <= end_date:
            items.append(
                make_item(
                    source="estimate",
                    event_type="estimate",
                    event_type_label="Estimate Issued",
                    title=f"Estimate: {estimate.estimate_number or estimate.id_estimate}",
                    item_date=estimate.issue_date,
                    status=estimate.status,
                    status_label=estimate.get_status_display() if hasattr(estimate, "get_status_display") else estimate.status,
                    priority="normal",
                    company=company,
                    description=estimate.description or estimate.notes or "",
                    url=company_url(company, f"estimates/{estimate.id_estimate}/"),
                    meta=f"${estimate.total}",
                )
            )

        if estimate.expiration_date and start_date <= estimate.expiration_date <= end_date:
            items.append(
                make_item(
                    source="estimate",
                    event_type="estimate",
                    event_type_label="Estimate Expiration",
                    title=f"Estimate Expires: {estimate.estimate_number or estimate.id_estimate}",
                    item_date=estimate.expiration_date,
                    status=estimate.status,
                    status_label=estimate.get_status_display() if hasattr(estimate, "get_status_display") else estimate.status,
                    priority="high",
                    company=company,
                    description=estimate.description or estimate.notes or "",
                    url=company_url(company, f"estimates/{estimate.id_estimate}/"),
                    meta=f"${estimate.total}",
                )
            )

    return items


def build_invoice_items(user, company, start_date, end_date):
    queryset = Invoice.objects.select_related("id_project").filter(id_company=company)

    if not user_can_see_company_wide(user, "invoices"):
        related_project_ids = user_related_project_ids(user, company)

        queryset = queryset.filter(
            Q(created_by=user)
            | Q(updated_by=user)
            | Q(generated_by=user)
            | Q(sent_by=user)
            | Q(voided_by=user)
            | Q(id_project_id__in=related_project_ids)
        ).distinct()

    queryset = queryset.filter(
        Q(issue_date__gte=start_date, issue_date__lte=end_date)
        | Q(due_date__gte=start_date, due_date__lte=end_date)
    ).order_by("issue_date", "due_date")

    items = []

    for invoice in queryset:
        if invoice.issue_date and start_date <= invoice.issue_date <= end_date:
            items.append(
                make_item(
                    source="invoice",
                    event_type="invoice",
                    event_type_label="Invoice Issued",
                    title=f"Invoice: {invoice.invoice_number or invoice.id_invoice}",
                    item_date=invoice.issue_date,
                    status=invoice.status,
                    status_label=invoice.get_status_display() if hasattr(invoice, "get_status_display") else invoice.status,
                    priority="normal",
                    company=company,
                    description=invoice.description or invoice.notes or "",
                    url=company_url(company, f"invoices/{invoice.id_invoice}/"),
                    meta=f"${invoice.total}",
                )
            )

        if invoice.due_date and start_date <= invoice.due_date <= end_date:
            priority = "normal"

            if invoice.balance_due and invoice.balance_due > 0:
                priority = "high"

            items.append(
                make_item(
                    source="invoice",
                    event_type="invoice",
                    event_type_label="Invoice Due",
                    title=f"Invoice Due: {invoice.invoice_number or invoice.id_invoice}",
                    item_date=invoice.due_date,
                    status=invoice.payment_status,
                    status_label=invoice.get_payment_status_display() if hasattr(invoice, "get_payment_status_display") else invoice.payment_status,
                    priority=priority,
                    company=company,
                    description=invoice.description or invoice.notes or "",
                    url=company_url(company, f"invoices/{invoice.id_invoice}/"),
                    meta=f"Balance: ${invoice.balance_due}",
                )
            )

    return items


def build_payment_items(user, company, start_date, end_date):
    queryset = (
        Payment.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "created_by",
            "verified_by",
        )
        .filter(
            id_company=company,
            payment_date__gte=start_date,
            payment_date__lte=end_date,
        )
        .order_by("payment_date")
    )

    if not user_can_see_company_wide(user, "payments"):
        related_project_ids = user_related_project_ids(user, company)

        queryset = queryset.filter(
            Q(created_by=user)
            | Q(verified_by=user)
            | Q(voided_by=user)
            | Q(id_project_id__in=related_project_ids)
        ).distinct()

    items = []

    for payment in queryset:
        priority = "high" if payment.status in ["pending_payment", "rejected"] else "normal"

        items.append(
            make_item(
                source="payment",
                event_type="payment",
                event_type_label="Payment",
                title=f"Payment: {payment.payment_number or payment.voucher_code or payment.id_payment}",
                item_date=payment.payment_date,
                status=payment.status,
                status_label=payment.get_status_display() if hasattr(payment, "get_status_display") else payment.status,
                priority=priority,
                company=company,
                description=payment.notes or payment.reference_code or "",
                url=company_url(company, f"payments/{payment.id_payment}/"),
                meta=f"${payment.amount}",
            )
        )

    return items


def item_matches_search(item, q):
    if not q:
        return True

    q_lower = q.lower().strip()

    searchable = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("meta") or ""),
            str(item.get("event_type_label") or ""),
            str(item.get("status_label") or ""),
        ]
    ).lower()

    return q_lower in searchable


def get_company_calendar_items(user, start_date, end_date, event_type=None, q=None, company=None):
    if not user or not user.is_authenticated:
        return []

    company = company or getattr(user, "id_company", None)

    if not company:
        return []

    items = []

    items.extend(build_manual_calendar_items(user, company, start_date, end_date))
    items.extend(build_notification_items(user, company, start_date, end_date))
    items.extend(build_project_items(user, company, start_date, end_date))
    items.extend(build_inspection_items(user, company, start_date, end_date))
    items.extend(build_estimate_items(user, company, start_date, end_date))
    items.extend(build_invoice_items(user, company, start_date, end_date))
    items.extend(build_payment_items(user, company, start_date, end_date))

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

    sorted_items = sorted(
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

    for index, item in enumerate(sorted_items, start=1):
        item["uid"] = f"calendar-item-{index}"

    return sorted_items


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