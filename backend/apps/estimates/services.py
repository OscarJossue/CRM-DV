import os
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO


from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.formats import date_format

from apps.core.ui_translation import company_language, translate_ui_text as ui
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


from .models import Estimate
from .models.choices import (
    ESTIMATE_CONVERT_ALLOWED_STATUSES,
    ESTIMATE_DECISION_ALLOWED_STATUSES,
    ESTIMATE_EDIT_ALLOWED_STATUSES,
    ESTIMATE_PROTECTED_STATUSES,
    ESTIMATE_SEND_ALLOWED_STATUSES,
    ESTIMATE_STATUS_APPROVED,
    ESTIMATE_STATUS_CANCELLED,
    ESTIMATE_STATUS_CONVERTED,
    ESTIMATE_STATUS_EXPIRED,
    ESTIMATE_STATUS_PENDING,
    ESTIMATE_STATUS_PENDING_SEND,
    ESTIMATE_STATUS_REJECTED,
    ESTIMATE_STATUS_SENT,
    ESTIMATE_STATUS_VIEWED,
)


MONEY_QUANTIZE = Decimal("0.01")

PUBLIC_ESTIMATE_DECISION_ALLOWED_STATUSES = [
    ESTIMATE_STATUS_SENT,
    ESTIMATE_STATUS_VIEWED,
]

PUBLIC_ESTIMATE_FINAL_STATUSES = [
    ESTIMATE_STATUS_APPROVED,
    ESTIMATE_STATUS_REJECTED,
    ESTIMATE_STATUS_CONVERTED,
    ESTIMATE_STATUS_CANCELLED,
]


class EstimatePublicFlowError(Exception):
    pass


def money(value):
    if value in [None, ""]:
        value = Decimal("0.00")

    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    return value.quantize(
        MONEY_QUANTIZE,
        rounding=ROUND_HALF_UP,
    )


def _to_decimal(value):
    try:
        if value in [None, ""]:
            return Decimal("0.00")

        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def generate_estimate_number(company):
    last_estimate = (
        Estimate.objects.filter(id_company=company)
        .exclude(estimate_number__isnull=True)
        .exclude(estimate_number="")
        .order_by("-id_estimate")
        .first()
    )

    if not last_estimate or not last_estimate.estimate_number:
        return "EST-000001"

    try:
        last_number = int(str(last_estimate.estimate_number).replace("EST-", ""))
    except (TypeError, ValueError):
        last_number = last_estimate.id_estimate or 0

    return f"EST-{last_number + 1:06d}"


def calculate_expiration_date(estimate):
    issue_date = estimate.issue_date or timezone.localdate()

    if hasattr(issue_date, "date"):
        issue_date = issue_date.date()

    validity_days = estimate.validity_days or 15

    return issue_date + timezone.timedelta(days=validity_days)


def refresh_estimate_status(estimate):
    today = timezone.localdate()
    expiration_date = calculate_expiration_date(estimate)
    update_fields = []

    if estimate.expiration_date != expiration_date:
        estimate.expiration_date = expiration_date
        update_fields.append("expiration_date")

    if (
        estimate.status not in ESTIMATE_PROTECTED_STATUSES
        and estimate.status != ESTIMATE_STATUS_EXPIRED
        and expiration_date < today
    ):
        estimate.status = ESTIMATE_STATUS_EXPIRED
        update_fields.append("status")

    if update_fields:
        update_fields.append("last_modified_at")
        estimate.save(update_fields=update_fields)

    return estimate


def get_estimate_validity_data(estimate):
    expiration_date = calculate_expiration_date(estimate)
    today = timezone.localdate()
    days_left = (expiration_date - today).days

    if days_left < 0:
        return {"label": "Expired", "class": "expired"}

    if days_left == 0:
        return {"label": "Expires today", "class": "danger"}

    if days_left <= 2:
        return {"label": f"{days_left} days left", "class": "danger"}

    if days_left <= 9:
        return {"label": f"{days_left} days left", "class": "warning"}

    return {"label": f"{days_left} days left", "class": "success"}


def _build_legacy_items_from_estimate_items(estimate):
    normalized_items = []

    for item in estimate.items.all():
        normalized_items.append(
            {
                "description": item.description,
                "quantity": float(item.quantity or Decimal("0.00")),
                "unit_price": float(item.unit_price or Decimal("0.00")),
                "total": float(item.total or Decimal("0.00")),
                "photo_path": getattr(item.photo, "path", "") if getattr(item, "photo", None) else "",
            }
        )

    return normalized_items


def _recalculate_from_estimate_items(estimate):
    subtotal = Decimal("0.00")

    for item in estimate.items.all():
        quantity = money(item.quantity or Decimal("0.00"))
        unit_price = money(item.unit_price or Decimal("0.00"))

        item.subtotal = money(quantity * unit_price)
        item.total = item.subtotal
        item.save(update_fields=["subtotal", "total"])

        subtotal += item.total

    return money(subtotal)


def _recalculate_from_legacy_json_items(estimate):
    subtotal = Decimal("0.00")
    normalized_items = []

    for item in estimate.detail_items or []:
        description = str(item.get("description", "")).strip()
        quantity = _to_decimal(item.get("quantity", 0))
        unit_price = _to_decimal(item.get("unit_price", 0))
        item_total = money(quantity * unit_price)

        normalized_items.append(
            {
                "description": description,
                "quantity": float(quantity),
                "unit_price": float(unit_price),
                "total": float(item_total),
            }
        )

        subtotal += item_total

    estimate.detail_items = normalized_items

    return money(subtotal)


@transaction.atomic
def recalculate_estimate(estimate: Estimate):
    has_estimate_items = estimate.pk and estimate.items.exists()

    if has_estimate_items:
        subtotal = _recalculate_from_estimate_items(estimate)
        estimate.detail_items = _build_legacy_items_from_estimate_items(estimate)
    else:
        subtotal = _recalculate_from_legacy_json_items(estimate)

    discount_amount = money(estimate.discount_amount or Decimal("0.00"))

    if discount_amount < Decimal("0.00"):
        discount_amount = Decimal("0.00")

    taxable_base = subtotal - discount_amount

    if taxable_base < Decimal("0.00"):
        taxable_base = Decimal("0.00")

    tax_amount = Decimal("0.00")

    if estimate.tax_enabled:
        tax_rate = money(estimate.tax_rate or Decimal("0.00"))
        tax_amount = money(taxable_base * tax_rate / Decimal("100"))

    estimate.subtotal = money(subtotal)
    estimate.discount_amount = money(discount_amount)
    estimate.tax = money(tax_amount)
    estimate.total = money(taxable_base + tax_amount)
    estimate.expiration_date = calculate_expiration_date(estimate)

    if not estimate.estimate_number:
        estimate.estimate_number = generate_estimate_number(estimate.id_company)

    estimate.save(
        update_fields=[
            "estimate_number",
            "detail_items",
            "subtotal",
            "discount_amount",
            "tax",
            "total",
            "expiration_date",
            "last_modified_at",
        ]
    )

    refresh_estimate_status(estimate)

    return estimate


def ensure_estimate_can_be_edited(estimate):
    if estimate.status not in ESTIMATE_EDIT_ALLOWED_STATUSES:
        raise ValueError("This estimate can no longer be edited because it is approved, converted or cancelled.")

    return True


@transaction.atomic
def estimate_create(**data):
    estimate = Estimate.objects.create(**data)

    if not estimate.estimate_number:
        estimate.estimate_number = generate_estimate_number(estimate.id_company)
        estimate.save(update_fields=["estimate_number"])

    recalculate_estimate(estimate)

    return estimate


@transaction.atomic
def estimate_update(estimate, **data):
    ensure_estimate_can_be_edited(estimate)

    allowed_fields = [
        "id_company",
        "id_client",
        "id_project",
        "logo",
        "description",
        "detail_items",
        "tax",
        "tax_enabled",
        "tax_rate",
        "discount_amount",
        "validity_days",
        "status",
        "notes",
        "client_billing_name",
        "client_billing_email",
        "client_billing_phone",
        "client_billing_address",
        "project_name",
        "project_address",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(estimate, field, data[field])

    estimate.full_clean()
    estimate.save()
    recalculate_estimate(estimate)

    return estimate


@transaction.atomic
def create_estimate(estimate, user=None, status=ESTIMATE_STATUS_PENDING_SEND):
    if not estimate.estimate_number:
        estimate.estimate_number = generate_estimate_number(estimate.id_company)

    estimate.status = status or ESTIMATE_STATUS_PENDING_SEND
    estimate.expiration_date = calculate_expiration_date(estimate)

    if user and user.is_authenticated:
        estimate.created_by = user
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save()
    recalculate_estimate(estimate)

    return estimate


@transaction.atomic
def update_estimate(estimate, user=None, status=None):
    ensure_estimate_can_be_edited(estimate)

    if status:
        estimate.status = status

    estimate.expiration_date = calculate_expiration_date(estimate)

    if user and user.is_authenticated:
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save()
    recalculate_estimate(estimate)

    return estimate


def get_public_estimate_by_token(token):
    """
    Get estimate by public token for the customer review page.
    No CRM login is required for this lookup.
    """
    try:
        return Estimate.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
        ).prefetch_related(
            "items",
        ).get(public_token=token)
    except Estimate.DoesNotExist as exc:
        raise Http404("Estimate review link not found.") from exc


def can_customer_decide_estimate(estimate):
    """Return True only for an active, unexpired customer review."""
    refresh_estimate_status(estimate)
    if estimate.expiration_date and estimate.expiration_date < timezone.localdate():
        return False
    return estimate.status in PUBLIC_ESTIMATE_DECISION_ALLOWED_STATUSES


def refresh_public_estimate_token(estimate, *, force=False):
    """
    Regenerate the customer token when a rejected estimate is edited or resent.
    This disables the old approval/rejection link and makes the next email link unique.
    """
    if not force and estimate.public_token:
        return estimate

    estimate.public_token = uuid.uuid4()
    estimate.public_token_refreshed_at = timezone.now()
    estimate.viewed_at = None

    estimate.save(
        update_fields=[
            "public_token",
            "public_token_refreshed_at",
            "viewed_at",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def reopen_rejected_estimate_after_edit(estimate, user=None):
    """
    After a rejected estimate is edited, move it back to pending_send and refresh
    its public token so the client can approve/reject the revised version only.
    """
    estimate.status = ESTIMATE_STATUS_PENDING_SEND
    estimate.rejected_at = None
    estimate.rejection_reason = ""
    estimate.approved_at = None
    estimate.viewed_at = None
    estimate.public_token = uuid.uuid4()
    estimate.public_token_refreshed_at = timezone.now()

    if user and getattr(user, "is_authenticated", False):
        estimate.updated_by = user

    estimate.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "approved_at",
            "viewed_at",
            "public_token",
            "public_token_refreshed_at",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def mark_estimate_as_viewed_publicly(estimate):
    """
    Mark an estimate as viewed from the public customer page.
    Final statuses stay unchanged and view-only.
    """
    estimate.refresh_from_db()
    refresh_estimate_status(estimate)

    if estimate.status != ESTIMATE_STATUS_SENT:
        return estimate

    estimate.status = ESTIMATE_STATUS_VIEWED
    estimate.viewed_at = timezone.now()
    estimate.save(update_fields=["status", "viewed_at", "last_modified_at"])

    return estimate


@transaction.atomic
def approve_estimate_publicly(estimate):
    """
    Approve an estimate from the public customer flow.
    This updates the CRM estimate directly and blocks future decision links.
    """
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)

    if not can_customer_decide_estimate(estimate):
        raise EstimatePublicFlowError("This estimate can no longer be approved.")

    estimate.status = ESTIMATE_STATUS_APPROVED
    estimate.approved_at = timezone.now()
    estimate.rejected_at = None
    estimate.rejection_reason = ""
    estimate.save(
        update_fields=[
            "status",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def reject_estimate_publicly(estimate, reason):
    """
    Reject an estimate from the public customer flow.
    The rejection reason is mandatory and is stored in the CRM.
    """
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    reason = (reason or "").strip()

    if not reason:
        raise EstimatePublicFlowError("A rejection reason is required.")

    if not can_customer_decide_estimate(estimate):
        raise EstimatePublicFlowError("This estimate can no longer be rejected.")

    estimate.status = ESTIMATE_STATUS_REJECTED
    estimate.rejected_at = timezone.now()
    estimate.rejection_reason = reason
    estimate.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def estimate_approve(estimate):
    if estimate.status not in ESTIMATE_DECISION_ALLOWED_STATUSES:
        raise ValueError("Only sent estimates can be approved.")

    estimate.status = ESTIMATE_STATUS_APPROVED
    estimate.approved_at = timezone.now()
    estimate.rejected_at = None
    estimate.rejection_reason = ""
    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def approve_estimate(estimate, user=None):
    if estimate.status not in ESTIMATE_DECISION_ALLOWED_STATUSES:
        raise ValueError("Only sent estimates can be approved.")

    estimate.status = ESTIMATE_STATUS_APPROVED
    estimate.approved_at = timezone.now()
    estimate.rejected_at = None
    estimate.rejection_reason = ""

    if user and user.is_authenticated:
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def estimate_reject(estimate, reason=""):
    if estimate.status not in ESTIMATE_DECISION_ALLOWED_STATUSES:
        raise ValueError("Only sent estimates can be rejected.")

    estimate.status = ESTIMATE_STATUS_REJECTED
    estimate.rejected_at = timezone.now()
    if reason:
        estimate.rejection_reason = reason.strip()
    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def reject_estimate(estimate, user=None, reason=""):
    if estimate.status not in ESTIMATE_DECISION_ALLOWED_STATUSES:
        raise ValueError("Only sent estimates can be rejected.")

    estimate.status = ESTIMATE_STATUS_REJECTED
    estimate.rejected_at = timezone.now()
    if reason:
        estimate.rejection_reason = reason.strip()

    if user and user.is_authenticated:
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def estimate_cancel(estimate):
    if estimate.status in [
        ESTIMATE_STATUS_APPROVED,
        ESTIMATE_STATUS_CONVERTED,
        ESTIMATE_STATUS_CANCELLED,
    ]:
        raise ValueError("Approved, converted or already cancelled estimates cannot be cancelled.")

    estimate.status = ESTIMATE_STATUS_CANCELLED
    estimate.full_clean()
    estimate.save(update_fields=["status", "last_modified_at"])

    return estimate


@transaction.atomic
def mark_estimate_as_sent(estimate, user=None):
    allowed_send_statuses = set(ESTIMATE_SEND_ALLOWED_STATUSES)

    original_status = estimate.status

    if original_status not in allowed_send_statuses:
        raise ValueError("Only pending, sent, viewed or rejected estimates can be sent.")

    recalculate_estimate(estimate)

    if original_status not in [ESTIMATE_STATUS_APPROVED, ESTIMATE_STATUS_CONVERTED]:
        refresh_estimate_status(estimate)

    if estimate.status == ESTIMATE_STATUS_EXPIRED:
        raise ValueError("Expired estimates cannot be sent.")

    estimate.status = ESTIMATE_STATUS_SENT

    estimate.sent_at = timezone.now()

    if user and user.is_authenticated:
        estimate.sent_by = user
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "sent_at",
            "sent_by",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate


def build_estimate_email_subject(estimate):
    with company_language(estimate):
        return f"{ui('Estimate')} {estimate.estimate_number or estimate.id_estimate}"


def build_estimate_email_text(estimate, custom_message="", public_estimate_url=""):
    with company_language(estimate):
        message = custom_message.strip() if custom_message else ""
        body = [
            f"{ui('Estimate')} {estimate.estimate_number or estimate.id_estimate}",
            "",
            f"{ui('Client')}: {estimate.client_billing_name or estimate.id_client}",
            f"{ui('Project')}: {estimate.project_name or '-'}",
            f"{ui('Total')}: ${estimate.total}",
            "",
        ]
        if message:
            body.extend([message, ""])
        if public_estimate_url:
            body.extend([
                ui("Review, approve or reject this estimate here:"),
                public_estimate_url,
                "",
            ])
        body.extend([
            ui("A PDF copy is attached for your records."),
            ui("Thank you."),
        ])
        return "\n".join(body)


def build_estimate_email_html(estimate, custom_message="", public_estimate_url=""):
    with company_language(estimate):
        message = custom_message.strip() if custom_message else ui("Thank you.")
        action_button = ""
        if public_estimate_url:
            action_button = f'''
            <p style="margin:24px 0;">
                <a href="{public_estimate_url}" style="display:inline-block;background:#212227;color:#ffffff;text-decoration:none;padding:13px 22px;border-radius:999px;font-weight:800;">
                    {ui("Review / Approve Estimate")}
                </a>
            </p>
            <p style="color:#637074;font-size:13px;">{ui("If the button does not work, copy and paste this link into your browser:")}<br>{public_estimate_url}</p>
            '''
        return f'''
        <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
            <h2>{ui("Estimate")} {estimate.estimate_number or estimate.id_estimate}</h2>
            <p>{ui("Please review your estimate information. You can approve or reject it from the secure review link below.")}</p>
            <table style="border-collapse:collapse;width:100%;max-width:620px;">
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Client")}</b></td><td style="padding:8px;border:1px solid #ddd;">{estimate.client_billing_name or estimate.id_client}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Project")}</b></td><td style="padding:8px;border:1px solid #ddd;">{estimate.project_name or "-"}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Subtotal")}</b></td><td style="padding:8px;border:1px solid #ddd;">${estimate.subtotal}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Tax")}</b></td><td style="padding:8px;border:1px solid #ddd;">${estimate.tax}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Total")}</b></td><td style="padding:8px;border:1px solid #ddd;">${estimate.total}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Expiration Date")}</b></td><td style="padding:8px;border:1px solid #ddd;">{_date_text(estimate.expiration_date)}</td></tr>
            </table>
            {action_button}
            <p>{message}</p>
        </div>
        '''


@transaction.atomic
def send_estimate_to_email(
    estimate,
    recipient_email,
    user=None,
    subject="",
    message="",
    public_estimate_url="",
):
    allowed_send_statuses = set(ESTIMATE_SEND_ALLOWED_STATUSES)

    original_status = estimate.status

    if original_status not in allowed_send_statuses:
        raise ValueError("Only pending, sent, viewed or rejected estimates can be sent.")

    if not recipient_email:
        raise ValueError("Recipient email is required.")

    recalculate_estimate(estimate)

    if original_status not in [ESTIMATE_STATUS_APPROVED, ESTIMATE_STATUS_CONVERTED]:
        refresh_estimate_status(estimate)

    if estimate.status == ESTIMATE_STATUS_EXPIRED:
        raise ValueError("Expired estimates cannot be sent.")

    email_subject = subject.strip() if subject else build_estimate_email_subject(estimate)
    text_body = build_estimate_email_text(
        estimate,
        custom_message=message,
        public_estimate_url=public_estimate_url,
    )
    html_body = build_estimate_email_html(
        estimate,
        custom_message=message,
        public_estimate_url=public_estimate_url,
    )

    from apps.smtp_settings.services import send_company_email

    pdf_filename = get_estimate_pdf_filename(estimate)
    pdf_content = build_estimate_pdf_bytes(estimate)

    sent_count = send_company_email(
        company=estimate.id_company,
        subject=email_subject,
        text_body=text_body,
        html_body=html_body,
        to_emails=[recipient_email],
        attachments=[(pdf_filename, pdf_content, "application/pdf")],
    )

    if sent_count <= 0:
        raise ValueError("The estimate email could not be sent.")

    estimate.status = ESTIMATE_STATUS_SENT

    estimate.sent_at = timezone.now()

    if user and user.is_authenticated:
        estimate.sent_by = user
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "sent_at",
            "sent_by",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate


@transaction.atomic
def mark_estimate_as_converted(estimate, invoice=None, user=None):
    if estimate.status not in ESTIMATE_CONVERT_ALLOWED_STATUSES:
        raise ValueError("Only approved estimates can be converted to invoice.")

    estimate.status = ESTIMATE_STATUS_CONVERTED
    estimate.converted_at = timezone.now()

    if invoice:
        estimate.converted_invoice = invoice

    if user and user.is_authenticated:
        estimate.updated_by = user

    estimate.full_clean()
    estimate.save(
        update_fields=[
            "status",
            "converted_at",
            "converted_invoice",
            "updated_by",
            "last_modified_at",
        ]
    )

    return estimate



PDF_MARGIN = 42
PDF_WIDTH, PDF_HEIGHT = letter
PDF_PRIMARY = colors.HexColor("#212227")
PDF_PRIMARY_DARK = colors.HexColor("#14171D")
PDF_MUTED = colors.HexColor("#637074")
PDF_ACCENT = colors.HexColor("#8693AB")
PDF_ACCENT_DARK = colors.HexColor("#5F718F")
PDF_ACCENT_SOFT = colors.HexColor("#AAB9CF")
PDF_ACCENT_PALE = colors.HexColor("#BDD4E7")
PDF_BORDER = colors.HexColor("#D6DDE8")
PDF_LIGHT = colors.HexColor("#F7F9FC")
PDF_ROW = colors.HexColor("#FBFCFE")
PDF_DANGER = colors.HexColor("#B91C1C")
PDF_SUCCESS = colors.HexColor("#0F766E")
PDF_WARNING = colors.HexColor("#B45309")


def get_estimate_pdf_filename(estimate: Estimate):
    base_name = estimate.estimate_number or f"estimate-{estimate.id_estimate}"
    return f"{base_name}.pdf"


def _money_text(value):
    return f"${money(value):,.2f}"


def _safe_text(value, default="-"):
    text = str(value or "").strip()
    return text if text else default


def _date_text(value):
    if not value:
        return "-"
    try:
        return date_format(value, format="DATE_FORMAT", use_l10n=True)
    except (AttributeError, TypeError, ValueError):
        return str(value)


def _company_logo_path(company):
    logo = getattr(company, "logo", None)

    if not logo:
        return None

    try:
        path = logo.path
    except (ValueError, NotImplementedError, AttributeError):
        return None

    if path and os.path.exists(path):
        return path

    return None


def _safe_image_path(value):
    if not value:
        return None
    try:
        path = value.path if hasattr(value, "path") else str(value)
    except (ValueError, NotImplementedError, AttributeError):
        return None
    return path if path and os.path.exists(path) else None


def _company_address_lines(company):
    parts = [
        getattr(company, "address", None),
        getattr(company, "city", None),
        getattr(company, "state", None),
        getattr(company, "country", None),
    ]

    return [str(part).strip() for part in parts if str(part or "").strip()]


def _wrap_text(text, max_width, font_name="Helvetica", font_size=9):
    text = _safe_text(text, "")
    wrapped_lines = []

    if not text:
        return [""]

    for raw_line in text.replace("\r", "").split("\n"):
        words = raw_line.split()

        if not words:
            wrapped_lines.append("")
            continue

        line = words[0]

        for word in words[1:]:
            candidate = f"{line} {word}"
            if stringWidth(candidate, font_name, font_size) <= max_width:
                line = candidate
            else:
                wrapped_lines.append(line)
                line = word

        wrapped_lines.append(line)

    return wrapped_lines or [""]


def _draw_wrapped_text(pdf, text, x, y, max_width, line_height=12, font_name="Helvetica", font_size=9, color=None):
    pdf.setFont(font_name, font_size)
    if color:
        pdf.setFillColor(color)

    for line in _wrap_text(text, max_width, font_name, font_size):
        if y < 70:
            _draw_page_footer(pdf)
            pdf.showPage()
            y = PDF_HEIGHT - 60
            pdf.setFont(font_name, font_size)
            if color:
                pdf.setFillColor(color)
        pdf.drawString(x, y, line[:190])
        y -= line_height

    return y


def _draw_shadow_card(pdf, x, y, width, height, fill_color=colors.white, stroke_color=PDF_BORDER, radius=12):
    pdf.setFillColor(colors.Color(0.08, 0.10, 0.14, alpha=0.055))
    pdf.roundRect(x + 2, y - 2, width, height, radius, fill=1, stroke=0)
    pdf.setFillColor(fill_color)
    pdf.setStrokeColor(stroke_color)
    pdf.setLineWidth(0.7)
    pdf.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def _draw_pill(pdf, x, y, text, fill_color, text_color=colors.white, width=None):
    pdf.setFont("Helvetica-Bold", 8.5)
    pill_width = width or max(58, stringWidth(text, "Helvetica-Bold", 8.5) + 20)
    pdf.setFillColor(fill_color)
    pdf.roundRect(x, y, pill_width, 19, 9.5, fill=1, stroke=0)
    pdf.setFillColor(text_color)
    pdf.drawCentredString(x + pill_width / 2, y + 6, text)
    return pill_width


def _draw_page_footer(pdf):
    pdf.setStrokeColor(PDF_BORDER)
    pdf.setLineWidth(0.6)
    pdf.line(PDF_MARGIN, 45, PDF_WIDTH - PDF_MARGIN, 45)
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(PDF_MARGIN, 29, ui("Thank you for your business"))
    pdf.drawRightString(PDF_WIDTH - PDF_MARGIN, 29, f"{ui('Page')} {pdf.getPageNumber()}")


def _estimate_status_key(estimate):
    status = _safe_text(getattr(estimate, "status", ""), "ESTIMATE").replace("_", " ").upper()
    if status == "CANCELLED":
        return "VOID"
    if status == "PENDING":
        return "PENDING SEND"
    return status


def _estimate_status_label(estimate):
    return ui(_estimate_status_key(estimate).title()).upper()


def _estimate_status_color(estimate):
    status = _estimate_status_key(estimate)
    if status in ["VOID", "REJECTED", "EXPIRED"]:
        return PDF_DANGER
    if status in ["APPROVED", "CONVERTED"]:
        return PDF_SUCCESS
    if status in ["SENT", "VIEWED"]:
        return PDF_ACCENT_DARK
    if status in ["PENDING SEND", "DRAFT"]:
        return PDF_WARNING if status == "PENDING SEND" else PDF_PRIMARY
    return PDF_PRIMARY


def _draw_document_stamp(pdf, label, color):
    if label not in ["VOID", "APPROVED", "CONVERTED", "REJECTED", "EXPIRED"]:
        return
    pdf.saveState()
    pdf.translate(PDF_WIDTH - 145, PDF_HEIGHT - 180)
    pdf.rotate(-15)
    try:
        pdf.setFillColor(colors.Color(color.red, color.green, color.blue, alpha=0.08))
        pdf.setStrokeColor(colors.Color(color.red, color.green, color.blue, alpha=0.45))
    except Exception:
        pdf.setFillColor(color)
        pdf.setStrokeColor(color)
    pdf.setLineWidth(2)
    width = 136 if len(label) > 7 else 116
    pdf.roundRect(-width/2, -17, width, 34, 10, fill=1, stroke=1)
    pdf.setFillColor(color)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(0, -7, label)
    pdf.restoreState()



def _draw_logo(pdf, company, x, y, width=96, height=56, use_dark=False):
    """Draw only the logo tile background according to the PDF style switch."""
    logo_path = _company_logo_path(company)
    logo_fill = PDF_PRIMARY_DARK if use_dark else colors.white
    logo_stroke = colors.Color(1, 1, 1, alpha=0.22) if use_dark else PDF_BORDER
    fallback_color = colors.white if use_dark else PDF_ACCENT_DARK

    pdf.setFillColor(colors.Color(0.08, 0.10, 0.14, alpha=0.05))
    pdf.roundRect(x + 2, y - 2, width, height, 14, fill=1, stroke=0)
    pdf.setFillColor(logo_fill)
    pdf.setStrokeColor(logo_stroke)
    pdf.setLineWidth(0.7)
    pdf.roundRect(x, y, width, height, 14, fill=1, stroke=1)

    if not logo_path:
        fallback = _safe_text(getattr(company, "name", None), "CRM")[:2].upper()
        pdf.setFillColor(fallback_color)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(x + width / 2, y + 20, fallback)
        return

    try:
        image = ImageReader(logo_path)
        image_width, image_height = image.getSize()
        max_width = width - 20
        max_height = height - 16
        scale = min(max_width / image_width, max_height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        pdf.drawImage(
            image,
            x + (width - draw_width) / 2,
            y + (height - draw_height) / 2,
            width=draw_width,
            height=draw_height,
            mask="auto",
        )
    except Exception:
        fallback = _safe_text(getattr(company, "name", None), "CRM")[:2].upper()
        pdf.setFillColor(fallback_color)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(x + width / 2, y + 20, fallback)


def _draw_header(pdf, estimate):
    company = estimate.id_company
    use_dark_logo_background = bool(getattr(estimate, "pdf_header_dark", False))
    header_height = 122
    header_y = PDF_HEIGHT - header_height

    pdf.setFillColor(PDF_LIGHT)
    pdf.rect(0, header_y, PDF_WIDTH, header_height, fill=1, stroke=0)
    pdf.setFillColor(PDF_ACCENT_PALE)
    pdf.rect(0, PDF_HEIGHT - 8, PDF_WIDTH, 8, fill=1, stroke=0)

    card_x = PDF_MARGIN
    card_y = header_y + 18
    card_w = PDF_WIDTH - PDF_MARGIN * 2
    card_h = header_height - 34
    pdf.setFillColor(colors.Color(0.08, 0.10, 0.14, alpha=0.045))
    pdf.roundRect(card_x + 2, card_y - 2, card_w, card_h, 18, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(PDF_BORDER)
    pdf.setLineWidth(0.6)
    pdf.roundRect(card_x, card_y, card_w, card_h, 18, fill=1, stroke=1)

    # Small neutral accent that never overlaps or hides the document title.
    pdf.setFillColor(colors.Color(0.741, 0.831, 0.906, alpha=0.32))
    pdf.roundRect(PDF_WIDTH - 188, card_y + 12, 128, card_h - 24, 14, fill=1, stroke=0)

    _draw_logo(pdf, company, PDF_MARGIN + 14, PDF_HEIGHT - 91, use_dark=use_dark_logo_background)

    company_x = PDF_MARGIN + 128
    max_company_width = PDF_WIDTH - PDF_MARGIN * 2 - 315
    company_name = _safe_text(getattr(company, "name", None), "Company")
    original_company_name = company_name
    while stringWidth(company_name, "Helvetica-Bold", 15) > max_company_width and len(company_name) > 16:
        company_name = company_name[:-2]
    if company_name != original_company_name:
        company_name = company_name.rstrip() + "…"

    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(company_x, PDF_HEIGHT - 39, company_name)

    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 8.3)
    y = PDF_HEIGHT - 54
    for line in _company_address_lines(company)[:2]:
        pdf.drawString(company_x, y, line[:62])
        y -= 11

    contact_parts = []
    if getattr(company, "phone", None):
        contact_parts.append(str(company.phone))
    if getattr(company, "email", None):
        contact_parts.append(str(company.email))
    if contact_parts:
        pdf.drawString(company_x, y, "  •  ".join(contact_parts)[:68])

    right_x = PDF_WIDTH - PDF_MARGIN - 18
    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawRightString(right_x, PDF_HEIGHT - 43, ui("Estimate").upper())
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(right_x, PDF_HEIGHT - 62, _safe_text(estimate.estimate_number or estimate.id_estimate))
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(right_x, PDF_HEIGHT - 77, f"{ui('Issue Date')}: {_date_text(estimate.issue_date)}")
    pdf.drawRightString(right_x, PDF_HEIGHT - 91, f"{ui('Valid Until')}: {_date_text(estimate.expiration_date)}")

    return header_y - 24


def _draw_info_card(pdf, title, rows, x, y, width, height):
    _draw_shadow_card(pdf, x, y - height, width, height, fill_color=colors.white, radius=14)
    pdf.setFillColor(PDF_ACCENT_PALE)
    pdf.roundRect(x, y - 24, width, 24, 14, fill=1, stroke=0)
    pdf.rect(x, y - 24, width, 12, fill=1, stroke=0)
    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x + 14, y - 16, title.upper())

    text_y = y - 39
    for label, value in rows:
        if text_y < y - height + 16:
            break
        pdf.setFillColor(PDF_MUTED)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(x + 14, text_y, f"{label.upper()}:")
        label_width = stringWidth(f"{label.upper()}:", "Helvetica-Bold", 7.5) + 5
        pdf.setFillColor(PDF_PRIMARY)
        pdf.setFont("Helvetica", 8.6)
        wrapped = _wrap_text(value, width - label_width - 28, "Helvetica", 8.6)
        line_y = text_y
        for line in wrapped[:3]:
            pdf.drawString(x + 14 + label_width, line_y, line[:90])
            line_y -= 10
        text_y = min(line_y, text_y - 15)


def _draw_label_value(pdf, label, value, x, y, width=230):
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(x, y, label.upper())
    y -= 13
    pdf.setFillColor(PDF_PRIMARY)
    y = _draw_wrapped_text(pdf, value, x, y, width, line_height=11, font_name="Helvetica", font_size=9)
    return y - 8


def _estimate_items(estimate):
    try:
        if estimate.items.exists():
            return [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total": item.total,
                    "photo_path": item.photo,
                }
                for item in estimate.items.all()
            ]
    except Exception:
        pass
    return estimate.detail_items or []


def _draw_items_table(pdf, estimate, y):
    left = PDF_MARGIN
    table_width = PDF_WIDTH - (PDF_MARGIN * 2)
    number_width = 30
    qty_width = 54
    unit_width = 78
    total_width = 88
    description_width = table_width - number_width - qty_width - unit_width - total_width
    header_height = 25

    def draw_table_header(current_y):
        pdf.setFillColor(PDF_PRIMARY)
        pdf.roundRect(left, current_y - header_height, table_width, header_height, 8, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(left + number_width / 2, current_y - 16, ui("No.").upper())
        pdf.drawString(left + number_width + 10, current_y - 16, ui("Description").upper())
        pdf.drawRightString(left + number_width + description_width + qty_width - 10, current_y - 16, ui("Quantity").upper())
        pdf.drawRightString(left + number_width + description_width + qty_width + unit_width - 10, current_y - 16, ui("Unit Price").upper())
        pdf.drawRightString(left + table_width - 12, current_y - 16, ui("Amount").upper())
        return current_y - header_height - 5

    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left, y, ui("Scope & Pricing"))
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(PDF_WIDTH - PDF_MARGIN, y, ui("Estimate pricing summary"))
    y -= 15
    y = draw_table_header(y)

    items = _estimate_items(estimate)

    if not items:
        _draw_shadow_card(pdf, left, y - 32, table_width, 32, fill_color=colors.white, radius=10)
        pdf.setFillColor(PDF_MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(left + 12, y - 19, ui("No items registered."))
        return y - 44

    for index, item in enumerate(items, start=1):
        description = _safe_text(item.get("description"), "-")
        quantity = _safe_text(item.get("quantity"), "0")
        unit_price = _money_text(item.get("unit_price") or 0)
        total = _money_text(item.get("total") or 0)
        photo_path = item.get("photo_path") or ""
        safe_photo_path = _safe_image_path(photo_path)
        text_width = description_width - (78 if safe_photo_path else 18)
        wrapped_description = _wrap_text(description, text_width, "Helvetica", 8.5)
        row_height = max(28, 11 * len(wrapped_description) + 12, 62 if safe_photo_path else 0)

        if y - row_height < 86:
            _draw_page_footer(pdf)
            pdf.showPage()
            y = PDF_HEIGHT - 60
            y = draw_table_header(y)

        fill = PDF_ROW if index % 2 == 0 else colors.white
        pdf.setFillColor(fill)
        pdf.setStrokeColor(PDF_BORDER)
        pdf.setLineWidth(0.5)
        pdf.rect(left, y - row_height, table_width, row_height, fill=1, stroke=1)

        current_x = left
        for column_width in [number_width, description_width, qty_width, unit_width]:
            current_x += column_width
            pdf.setStrokeColor(PDF_BORDER)
            pdf.line(current_x, y, current_x, y - row_height)

        pdf.setFillColor(PDF_PRIMARY)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawCentredString(left + number_width / 2, y - 16, str(index))

        text_x = left + number_width + 10
        if safe_photo_path:
            try:
                image = ImageReader(safe_photo_path)
                image_width, image_height = image.getSize()
                max_image_width = 55
                max_image_height = 44
                scale = min(max_image_width / image_width, max_image_height / image_height)
                draw_width = image_width * scale
                draw_height = image_height * scale
                image_x = left + number_width + 10
                image_y = y - row_height + (row_height - draw_height) / 2
                pdf.drawImage(image, image_x, image_y, width=draw_width, height=draw_height, mask="auto")
                text_x = left + number_width + 74
            except Exception:
                text_x = left + number_width + 10

        pdf.setFont("Helvetica", 8.5)
        text_y = y - 14
        for line in wrapped_description:
            pdf.drawString(text_x, text_y, line[:110])
            text_y -= 11

        qty_right = left + number_width + description_width + qty_width - 10
        unit_right = qty_right + unit_width
        total_right = left + table_width - 12
        pdf.setFont("Helvetica", 8.5)
        pdf.drawRightString(qty_right, y - 16, quantity)
        pdf.drawRightString(unit_right, y - 16, unit_price)
        pdf.setFont("Helvetica-Bold", 8.7)
        pdf.drawRightString(total_right, y - 16, total)
        y -= row_height

    return y - 14


def _draw_totals(pdf, estimate, y):
    box_width = 245
    x = PDF_WIDTH - PDF_MARGIN - box_width
    rows = [
        (ui("Subtotal"), _money_text(estimate.subtotal), False),
        (ui("Discount"), _money_text(estimate.discount_amount), False),
        (ui("Tax"), _money_text(estimate.tax), False),
        (ui("Grand Total"), _money_text(estimate.total), True),
    ]

    if y < 170:
        _draw_page_footer(pdf)
        pdf.showPage()
        y = PDF_HEIGHT - 70

    row_height = 27
    total_height = row_height * len(rows) + 14
    _draw_shadow_card(pdf, x, y - total_height, box_width, total_height, fill_color=colors.white, radius=14)

    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 14, y - 18, ui("Summary"))

    row_top = y - 31
    for index, (label, value, is_total) in enumerate(rows):
        row_y = row_top - (row_height * (index + 1))
        if is_total:
            pdf.setFillColor(PDF_PRIMARY)
            pdf.roundRect(x + 8, row_y + 3, box_width - 16, row_height - 3, 8, fill=1, stroke=0)
            text_color = colors.white
            font_name = "Helvetica-Bold"
        else:
            pdf.setFillColor(PDF_LIGHT if index % 2 == 0 else colors.white)
            pdf.rect(x + 8, row_y + 3, box_width - 16, row_height - 3, fill=1, stroke=0)
            text_color = PDF_PRIMARY
            font_name = "Helvetica"

        pdf.setFillColor(text_color)
        pdf.setFont(font_name, 9)
        pdf.drawString(x + 18, row_y + 11, label)
        pdf.drawRightString(x + box_width - 18, row_y + 11, value)

    return y - total_height - 18


def _draw_notes_terms(pdf, title, text, x, y, width, height):
    if y - height < 60:
        _draw_page_footer(pdf)
        pdf.showPage()
        y = PDF_HEIGHT - 60

    _draw_shadow_card(pdf, x, y - height, width, height, fill_color=PDF_LIGHT, radius=14)
    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x + 14, y - 18, title)
    y_text = y - 35
    _draw_wrapped_text(pdf, text, x + 14, y_text, width - 28, line_height=10.5, font_name="Helvetica", font_size=8.2, color=PDF_MUTED)
    return y - height - 12


def _build_estimate_pdf_bytes(estimate: Estimate):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"{ui('Estimate')} {estimate.estimate_number or estimate.id_estimate}")

    y = _draw_header(pdf, estimate)
    left_x = PDF_MARGIN
    gap = 16
    card_width = (PDF_WIDTH - PDF_MARGIN * 2 - gap) / 2
    card_height = 112
    right_x = left_x + card_width + gap

    client_name = estimate.client_billing_name or getattr(estimate.id_client, "name", "")
    billing_email = estimate.client_billing_email or getattr(estimate.id_client, "email", "")
    billing_phone = estimate.client_billing_phone or getattr(estimate.id_client, "phone", "")
    billing_address = estimate.client_billing_address or getattr(estimate.id_client, "address", "")
    project_name = estimate.project_name or getattr(estimate.id_project, "name", "No project")
    project_address = estimate.project_address or getattr(estimate.id_project, "project_address", "")

    _draw_info_card(
        pdf,
        ui("Client Information"),
        [
            (ui("Client"), client_name),
            (ui("Email"), billing_email),
            (ui("Phone"), billing_phone),
            (ui("Address"), billing_address),
        ],
        left_x,
        y,
        card_width,
        card_height,
    )

    _draw_info_card(
        pdf,
        ui("Project Information"),
        [
            (ui("Project"), project_name),
            (ui("Location"), project_address),
            (ui("Estimate Date"), _date_text(estimate.issue_date)),
            (ui("Valid Until"), _date_text(estimate.expiration_date)),
        ],
        right_x,
        y,
        card_width,
        card_height,
    )

    y = y - card_height - 26

    if estimate.description:
        desc_height = 58
        _draw_notes_terms(pdf, ui("Scope / Description"), estimate.description, PDF_MARGIN, y, PDF_WIDTH - PDF_MARGIN * 2, desc_height)
        y -= desc_height + 22

    if y < 180:
        _draw_page_footer(pdf)
        pdf.showPage()
        y = PDF_HEIGHT - 60

    y = _draw_items_table(pdf, estimate, y)
    totals_y = _draw_totals(pdf, estimate, y)

    notes_text = estimate.notes or ui("This estimate is based on the scope and pricing shown above. Please review all details before approval.")
    if totals_y > 130:
        _draw_notes_terms(pdf, ui("Notes / Terms"), notes_text, PDF_MARGIN, totals_y, PDF_WIDTH - PDF_MARGIN * 2 - 265, 88)
    else:
        _draw_notes_terms(pdf, ui("Notes / Terms"), notes_text, PDF_MARGIN, y, PDF_WIDTH - PDF_MARGIN * 2, 88)

    _draw_page_footer(pdf)
    pdf.save()
    return buffer.getvalue()


def build_estimate_pdf_bytes(estimate: Estimate):
    with company_language(estimate):
        return _build_estimate_pdf_bytes(estimate)


def estimate_pdf_response(estimate: Estimate):
    recalculate_estimate(estimate)
    refresh_estimate_status(estimate)

    filename = get_estimate_pdf_filename(estimate)
    response = HttpResponse(build_estimate_pdf_bytes(estimate), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response

def create_estimates(**data):
    return estimate_create(**data)


def update_estimates(instance, **data):
    return estimate_update(instance, **data)