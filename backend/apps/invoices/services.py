import os
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

from .models import Invoice, InvoiceItem
from .models.choices import (
    INVOICE_EDITABLE_STATUSES,
    INVOICE_GENERATE_ALLOWED_STATUSES,
    INVOICE_PAYMENT_STATUS_OVERPAID,
    INVOICE_PAYMENT_STATUS_PAID,
    INVOICE_PAYMENT_STATUS_PARTIAL,
    INVOICE_PAYMENT_STATUS_UNPAID,
    INVOICE_PAYMENT_STATUS_VOID,
    INVOICE_PDF_ALLOWED_STATUSES,
    INVOICE_SEND_ALLOWED_STATUSES,
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_PENDING_SEND,
    INVOICE_STATUS_SENT,
    INVOICE_STATUS_VOID,
    INVOICE_VOID_ALLOWED_STATUSES,
)


MONEY_QUANTIZE = Decimal("0.01")


def money(value):
    if value in [None, ""]:
        value = Decimal("0.00")

    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            value = Decimal("0.00")

    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def _to_decimal(value):
    try:
        if value in [None, ""]:
            return Decimal("0.00")
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def get_project_name(project):
    if not project:
        return ""

    for field_name in ["name", "project_name", "title"]:
        value = getattr(project, field_name, None)
        if value:
            return str(value).strip()

    return ""


def get_project_address(project):
    if not project:
        return ""

    for field_name in ["address", "project_address", "location"]:
        value = getattr(project, field_name, None)
        if value:
            return str(value).strip()

    return ""


def get_client_billing_name(client):
    if not client:
        return ""
    return getattr(client, "name", "") or ""


def get_client_billing_email(client):
    if not client:
        return ""

    for field_name in ["email", "client_email", "billing_email", "contact_email"]:
        value = getattr(client, field_name, None)
        if value:
            return value

    return ""


def get_client_billing_dni(client):
    if not client:
        return ""

    for field_name in ["dni", "tax_id", "identification_number", "document_number"]:
        value = getattr(client, field_name, None)
        if value:
            return str(value).strip()

    return ""


def get_client_billing_phone(client):
    if not client:
        return ""

    for field_name in ["phone", "client_phone", "billing_phone", "contact_phone"]:
        value = getattr(client, field_name, None)
        if value:
            return value

    return ""


def get_client_billing_address(client):
    if not client:
        return ""

    address_parts = []

    address = getattr(client, "address", None)
    city = getattr(client, "city", None)
    state = getattr(client, "state", None)

    if address:
        address_parts.append(str(address).strip())

    city_state = ", ".join([str(value).strip() for value in [city, state] if value])

    if city_state:
        address_parts.append(city_state)

    return "\n".join(address_parts)


def generate_invoice_number(company):
    last_invoice = (
        Invoice.objects.filter(id_company=company)
        .exclude(invoice_number__isnull=True)
        .exclude(invoice_number="")
        .order_by("-id_invoice")
        .first()
    )

    if not last_invoice or not last_invoice.invoice_number:
        return "INV-000001"

    try:
        last_number = int(str(last_invoice.invoice_number).replace("INV-", ""))
    except (TypeError, ValueError):
        last_number = last_invoice.id_invoice or 0

    return f"INV-{last_number + 1:06d}"


def get_payment_status_from_amounts(total, paid_amount, invoice_status=None):
    total = money(total)
    paid_amount = money(paid_amount)

    if invoice_status == INVOICE_STATUS_VOID:
        return INVOICE_PAYMENT_STATUS_VOID

    if paid_amount == Decimal("0.00"):
        return INVOICE_PAYMENT_STATUS_UNPAID

    if paid_amount < total:
        return INVOICE_PAYMENT_STATUS_PARTIAL

    if paid_amount == total:
        return INVOICE_PAYMENT_STATUS_PAID

    return INVOICE_PAYMENT_STATUS_OVERPAID


def update_invoice_balance_fields(invoice):
    total = money(invoice.total)
    paid_amount = money(invoice.paid_amount)

    if invoice.status == INVOICE_STATUS_VOID:
        invoice.paid_amount = paid_amount
        invoice.balance_due = Decimal("0.00")
        invoice.balance = Decimal("0.00")
        invoice.payment_status = INVOICE_PAYMENT_STATUS_VOID
        return invoice

    invoice.paid_amount = paid_amount

    balance_due = total - paid_amount

    if balance_due < Decimal("0.00"):
        balance_due = Decimal("0.00")

    invoice.balance_due = money(balance_due)
    invoice.balance = invoice.balance_due

    invoice.payment_status = get_payment_status_from_amounts(
        total=total,
        paid_amount=paid_amount,
        invoice_status=invoice.status,
    )

    return invoice


def ensure_invoice_has_required_relations(invoice):
    if not invoice.id_company_id:
        raise ValueError("Invoice company is required.")

    if not invoice.id_client_id:
        raise ValueError("Invoice client is required.")

    if not invoice.id_project_id:
        raise ValueError("Invoice project is required. Select an existing project before generating the invoice.")

    if invoice.id_client_id != invoice.id_project.id_client_id:
        raise ValueError("Invoice project must belong to the selected client.")

    if invoice.id_company_id != invoice.id_project.id_company_id:
        raise ValueError("Invoice project must belong to the selected company.")

    if invoice.id_client.id_company_id != invoice.id_company_id:
        raise ValueError("Invoice client must belong to the selected company.")

    return True


def sync_invoice_snapshots(invoice):
    ensure_invoice_has_required_relations(invoice)

    invoice.project_name = get_project_name(invoice.id_project)

    if not invoice.project_address:
        invoice.project_address = get_project_address(invoice.id_project)

    if not invoice.client_billing_name:
        invoice.client_billing_name = get_client_billing_name(invoice.id_client)

    if not invoice.client_billing_email:
        invoice.client_billing_email = get_client_billing_email(invoice.id_client)

    if not invoice.client_billing_phone:
        invoice.client_billing_phone = get_client_billing_phone(invoice.id_client)

    if not invoice.client_billing_dni:
        invoice.client_billing_dni = get_client_billing_dni(invoice.id_client)

    if not invoice.client_billing_address:
        invoice.client_billing_address = get_client_billing_address(invoice.id_client)

    return invoice




def sync_related_project_invoice_status(project):
    if not project:
        return

    try:
        from apps.projects.models import (
            PROJECT_INVOICE_STATUS_ATTACHED,
            PROJECT_INVOICE_STATUS_NO_INVOICE,
            Project,
        )
    except Exception:
        return

    project_id = getattr(project, "id_project", None) or getattr(project, "pk", None)
    if not project_id:
        return

    project_instance = project if isinstance(project, Project) else Project.objects.filter(id_project=project_id).first()
    if not project_instance:
        return

    has_invoices = Invoice.objects.filter(id_project_id=project_id).exists()
    next_status = PROJECT_INVOICE_STATUS_ATTACHED if has_invoices else PROJECT_INVOICE_STATUS_NO_INVOICE

    if project_instance.invoice_status != next_status:
        project_instance.invoice_status = next_status
        project_instance.save(update_fields=["invoice_status", "updated_at"])

def _build_legacy_items_from_invoice_items(invoice):
    normalized_items = []

    for item in invoice.items.all():
        normalized_items.append(
            {
                "description": item.description,
                "quantity": float(item.quantity or Decimal("0.00")),
                "unit_price": float(item.unit_price or Decimal("0.00")),
                "total": float(item.total or Decimal("0.00")),
            }
        )

    return normalized_items


def _recalculate_from_invoice_items(invoice):
    subtotal = Decimal("0.00")

    for item in invoice.items.all():
        quantity = money(item.quantity or Decimal("0.00"))
        unit_price = money(item.unit_price or Decimal("0.00"))

        item.subtotal = money(quantity * unit_price)
        item.total = item.subtotal
        item.taxable = True

        item.save(update_fields=["subtotal", "total", "taxable"])

        subtotal += item.total

    return money(subtotal)


def _recalculate_from_legacy_json_items(invoice):
    subtotal = Decimal("0.00")
    normalized_items = []

    for item in invoice.detail_items or []:
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

    invoice.detail_items = normalized_items

    return money(subtotal)


def _calculate_paid_amount_from_payments(invoice):
    """Return the real paid amount for an invoice.

    The current payments workflow uses PaymentAllocation for cash payments and
    ClientCreditMovement for consumed credit. The old direct Payment.id_invoice
    relation is kept only for legacy records.
    """
    try:
        from django.db.models import Sum

        from apps.payments.models import ClientCreditMovement, Payment, PaymentAllocation
        from apps.payments.models.choices import (
            CREDIT_MOVEMENT_APPLIED,
            CREDIT_MOVEMENT_VOIDED,
            PAYMENT_CONFIRMED_STATUSES,
        )

        allocation_total = (
            PaymentAllocation.objects.filter(
                id_invoice=invoice,
                id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        legacy_total = (
            Payment.objects.filter(
                id_invoice=invoice,
                status__in=PAYMENT_CONFIRMED_STATUSES,
                allocations__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        credit_applied_total = (
            ClientCreditMovement.objects.filter(
                id_invoice=invoice,
                movement_type=CREDIT_MOVEMENT_APPLIED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        credit_voided_total = (
            ClientCreditMovement.objects.filter(
                id_invoice=invoice,
                movement_type=CREDIT_MOVEMENT_VOIDED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        return money(
            allocation_total
            + legacy_total
            + credit_applied_total
            - credit_voided_total
        )

    except Exception:
        return money(invoice.paid_amount)


@transaction.atomic
def recalculate_invoice(invoice: Invoice):
    ensure_invoice_has_required_relations(invoice)

    has_invoice_items = invoice.pk and invoice.items.exists()

    if has_invoice_items:
        subtotal = _recalculate_from_invoice_items(invoice)
        invoice.detail_items = _build_legacy_items_from_invoice_items(invoice)
    else:
        subtotal = _recalculate_from_legacy_json_items(invoice)

    discount_amount = money(invoice.discount_amount or Decimal("0.00"))

    if discount_amount < Decimal("0.00"):
        discount_amount = Decimal("0.00")

    taxable_base = subtotal - discount_amount

    if taxable_base < Decimal("0.00"):
        taxable_base = Decimal("0.00")

    tax_amount = Decimal("0.00")

    if invoice.tax_enabled:
        tax_rate = money(invoice.tax_rate or Decimal("0.00"))
        tax_amount = money(taxable_base * tax_rate / Decimal("100"))

    invoice.subtotal = money(subtotal)
    invoice.discount_amount = money(discount_amount)
    invoice.tax = money(tax_amount)
    invoice.total = money(taxable_base + tax_amount)

    if invoice.status != INVOICE_STATUS_VOID:
        invoice.paid_amount = _calculate_paid_amount_from_payments(invoice)

    sync_invoice_snapshots(invoice)
    update_invoice_balance_fields(invoice)

    if not invoice.invoice_number:
        invoice.invoice_number = generate_invoice_number(invoice.id_company)

    invoice.save(
        update_fields=[
            "invoice_number",
            "detail_items",
            "client_billing_name",
            "client_billing_email",
            "client_billing_phone",
            "client_billing_dni",
            "client_billing_address",
            "project_name",
            "project_address",
            "subtotal",
            "discount_amount",
            "tax_enabled",
            "tax_rate",
            "tax",
            "total",
            "balance",
            "paid_amount",
            "balance_due",
            "payment_status",
            "last_modified_at",
        ]
    )

    return invoice


def ensure_invoice_can_be_edited(invoice):
    if invoice.status not in INVOICE_EDITABLE_STATUSES:
        raise ValueError("Only draft invoices can be edited.")
    return True


def ensure_invoice_can_be_generated(invoice):
    if invoice.status not in INVOICE_GENERATE_ALLOWED_STATUSES:
        raise ValueError("Only draft invoices can be generated.")
    return True


def ensure_invoice_can_be_sent(invoice):
    if invoice.status not in INVOICE_SEND_ALLOWED_STATUSES:
        raise ValueError("Only pending send or sent invoices can be sent.")
    return True


def ensure_invoice_can_be_voided(invoice):
    if invoice.status not in INVOICE_VOID_ALLOWED_STATUSES:
        raise ValueError("Only pending send or sent invoices can be voided.")
    return True


def ensure_invoice_can_download_pdf(invoice):
    if invoice.status not in INVOICE_PDF_ALLOWED_STATUSES:
        raise ValueError("This invoice status cannot download PDF.")
    return True


def prepare_invoice_initial_from_estimate(estimate):
    if estimate.status != "approved":
        raise ValueError("Only approved estimates can be used to create invoices.")

    return {
        "id_client": estimate.id_client,
        "id_project": estimate.id_project if estimate.id_project_id else None,
        "id_estimate": estimate,
        "client_billing_name": estimate.client_billing_name,
        "client_billing_email": estimate.client_billing_email,
        "client_billing_phone": estimate.client_billing_phone,
        "client_billing_dni": getattr(estimate, "client_billing_dni", None) or get_client_billing_dni(estimate.id_client),
        "client_billing_address": estimate.client_billing_address,
        "project_name": get_project_name(estimate.id_project) if estimate.id_project_id else estimate.project_name,
        "project_address": estimate.project_address or "",
        "description": estimate.description,
        "tax_enabled": estimate.tax_enabled,
        "tax_rate": estimate.tax_rate,
        "discount_amount": estimate.discount_amount,
        "notes": estimate.notes,
        "pdf_header_dark": getattr(estimate, "pdf_header_dark", False),
    }


def prepare_invoice_items_initial_from_estimate(estimate):
    if estimate.status != "approved":
        raise ValueError("Only approved estimates can be used to create invoice items.")

    items_initial = []

    if hasattr(estimate, "items") and estimate.items.exists():
        for estimate_item in estimate.items.all():
            items_initial.append(
                {
                    "description": estimate_item.description,
                    "quantity": estimate_item.quantity,
                    "unit_price": estimate_item.unit_price,
                }
            )
    else:
        for item in estimate.detail_items or []:
            items_initial.append(
                {
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 1),
                    "unit_price": item.get("unit_price", 0),
                }
            )

    return items_initial


def prepare_invoice_items_initial_from_project(project):
    """Build the single editable line item used for a project invoice.

    The project is only a source snapshot. The resulting invoice item remains a
    normal editable form row and is not kept synchronized after the user edits
    it.
    """
    if not project:
        return []

    description = (getattr(project, "description", None) or "").strip()
    if not description:
        description = get_project_name(project) or "Project services"

    return [
        {
            "description": description,
            "quantity": Decimal("1.00"),
            "unit_price": money(getattr(project, "contract_amount", Decimal("0.00"))),
        }
    ]


@transaction.atomic
def create_invoice(invoice, user=None, status=INVOICE_STATUS_DRAFT):
    ensure_invoice_has_required_relations(invoice)

    if not invoice.invoice_number:
        invoice.invoice_number = generate_invoice_number(invoice.id_company)

    invoice.status = status or INVOICE_STATUS_DRAFT

    sync_invoice_snapshots(invoice)
    update_invoice_balance_fields(invoice)

    if user and user.is_authenticated:
        invoice.created_by = user
        invoice.updated_by = user

    invoice.full_clean()
    invoice.save()
    sync_related_project_invoice_status(invoice.id_project)

    return invoice


@transaction.atomic
def update_invoice(invoice, user=None):
    ensure_invoice_can_be_edited(invoice)
    ensure_invoice_has_required_relations(invoice)

    previous_project_id = None
    if invoice.pk:
        previous_project_id = (
            Invoice.objects.filter(pk=invoice.pk).values_list("id_project_id", flat=True).first()
        )

    sync_invoice_snapshots(invoice)
    update_invoice_balance_fields(invoice)

    if user and user.is_authenticated:
        invoice.updated_by = user

    invoice.full_clean()
    invoice.save()

    if previous_project_id and previous_project_id != invoice.id_project_id:
        sync_related_project_invoice_status(previous_project_id)
    sync_related_project_invoice_status(invoice.id_project)

    return invoice


@transaction.atomic
def generate_invoice(invoice, user=None):
    ensure_invoice_can_be_generated(invoice)
    ensure_invoice_has_required_relations(invoice)

    if invoice.id_estimate and invoice.id_estimate.status != "approved":
        raise ValueError("Only approved estimates can generate invoices.")

    recalculate_invoice(invoice)

    invoice.status = INVOICE_STATUS_PENDING_SEND
    invoice.generated_at = timezone.now()
    invoice.paid_amount = Decimal("0.00")
    invoice.balance_due = money(invoice.total)
    invoice.balance = invoice.balance_due
    invoice.payment_status = INVOICE_PAYMENT_STATUS_UNPAID

    if user and user.is_authenticated:
        invoice.generated_by = user
        invoice.updated_by = user

    invoice.full_clean()
    invoice.save(
        update_fields=[
            "status",
            "generated_at",
            "generated_by",
            "updated_by",
            "paid_amount",
            "balance_due",
            "balance",
            "payment_status",
            "last_modified_at",
        ]
    )

    if invoice.id_estimate:
        try:
            from apps.estimates.services import mark_estimate_as_converted

            mark_estimate_as_converted(
                estimate=invoice.id_estimate,
                invoice=invoice,
                user=user,
            )
        except Exception:
            estimate = invoice.id_estimate
            estimate.status = "converted"

            if hasattr(estimate, "converted_at"):
                estimate.converted_at = timezone.now()

            if hasattr(estimate, "converted_invoice"):
                estimate.converted_invoice = invoice

            if user and user.is_authenticated and hasattr(estimate, "updated_by"):
                estimate.updated_by = user

            update_fields = ["status"]

            if hasattr(estimate, "converted_at"):
                update_fields.append("converted_at")

            if hasattr(estimate, "converted_invoice"):
                update_fields.append("converted_invoice")

            if user and user.is_authenticated and hasattr(estimate, "updated_by"):
                update_fields.append("updated_by")

            if hasattr(estimate, "last_modified_at"):
                update_fields.append("last_modified_at")

            estimate.save(update_fields=update_fields)

    try:
        from apps.payments.services import create_invoice_financial_movement

        create_invoice_financial_movement(invoice=invoice, user=user)
    except Exception:
        pass

    sync_related_project_invoice_status(invoice.id_project)

    return invoice


@transaction.atomic
def invoice_mark_sent(invoice):
    ensure_invoice_can_be_sent(invoice)

    invoice.status = INVOICE_STATUS_SENT
    invoice.sent_at = timezone.now()
    invoice.full_clean()
    invoice.save(update_fields=["status", "sent_at", "last_modified_at"])

    return invoice


def invoice_mark_paid(invoice):
    raise ValueError("Invoices cannot be marked as paid manually. Register a payment instead.")


def invoice_cancel(invoice):
    raise ValueError("Invoices cannot be cancelled. Use void invoice if there are no confirmed payments.")


def build_invoice_email_subject(invoice):
    with company_language(invoice):
        return f"{ui('Invoice')} {invoice.invoice_number or invoice.id_invoice}"


def build_invoice_email_text(invoice, custom_message=""):
    with company_language(invoice):
        message = custom_message.strip() if custom_message else ""
        body = [
            f"{ui('Invoice')} {invoice.invoice_number or invoice.id_invoice}",
            "",
            f"{ui('Client')}: {invoice.client_billing_name or invoice.id_client}",
            *([f"DNI / Tax ID: {invoice.client_billing_dni}"] if invoice.client_billing_dni else []),
            f"{ui('Project')}: {invoice.project_name or get_project_name(invoice.id_project)}",
            f"{ui('Total')}: ${invoice.total}",
            f"{ui('Balance Due')}: ${invoice.balance_due}",
            "",
        ]
        if message:
            body.extend([message, ""])
        body.extend([ui("Please review the invoice information."), ui("Thank you.")])
        return "\n".join(body)


def build_invoice_email_html(invoice, custom_message=""):
    with company_language(invoice):
        message = custom_message.strip() if custom_message else ui("Thank you.")
        return f"""
        <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
            <h2>{ui("Invoice")} {invoice.invoice_number or invoice.id_invoice}</h2>
            <p>{ui("Please review your invoice information.")}</p>
            <table style="border-collapse:collapse;width:100%;max-width:620px;">
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Client")}</b></td><td style="padding:8px;border:1px solid #ddd;">{invoice.client_billing_name or invoice.id_client}</td></tr>
                {f'<tr><td style="padding:8px;border:1px solid #ddd;"><b>DNI / Tax ID</b></td><td style="padding:8px;border:1px solid #ddd;">{invoice.client_billing_dni}</td></tr>' if invoice.client_billing_dni else ''}
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Project")}</b></td><td style="padding:8px;border:1px solid #ddd;">{invoice.project_name or get_project_name(invoice.id_project)}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Total")}</b></td><td style="padding:8px;border:1px solid #ddd;">${invoice.total}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Paid Amount")}</b></td><td style="padding:8px;border:1px solid #ddd;">${invoice.paid_amount}</td></tr>
                <tr><td style="padding:8px;border:1px solid #ddd;"><b>{ui("Balance Due")}</b></td><td style="padding:8px;border:1px solid #ddd;">${invoice.balance_due}</td></tr>
            </table>
            <p>{message}</p>
        </div>
        """


@transaction.atomic
def send_invoice_to_email(invoice, recipient_email, user=None, subject="", message=""):
    ensure_invoice_can_be_sent(invoice)
    ensure_invoice_has_required_relations(invoice)

    if not recipient_email:
        raise ValueError("Recipient email is required.")

    recalculate_invoice(invoice)

    email_subject = subject.strip() if subject else build_invoice_email_subject(invoice)
    text_body = build_invoice_email_text(invoice, custom_message=message)
    html_body = build_invoice_email_html(invoice, custom_message=message)

    from apps.smtp_settings.services import send_company_email

    pdf_filename = get_invoice_pdf_filename(invoice)
    pdf_content = build_invoice_pdf_bytes(invoice)

    sent_count = send_company_email(
        company=invoice.id_company,
        subject=email_subject,
        text_body=text_body,
        html_body=html_body,
        to_emails=[recipient_email],
        attachments=[(pdf_filename, pdf_content, "application/pdf")],
    )

    if sent_count <= 0:
        raise ValueError("The invoice email could not be sent.")

    invoice.status = INVOICE_STATUS_SENT
    invoice.sent_at = timezone.now()

    if user and user.is_authenticated:
        invoice.sent_by = user
        invoice.updated_by = user

    invoice.full_clean()
    invoice.save(update_fields=["status", "sent_at", "sent_by", "updated_by", "last_modified_at"])

    return invoice


def ensure_invoice_has_no_confirmed_payments(invoice):
    try:
        from apps.payments.models import ClientCreditMovement, Payment, PaymentAllocation
        from apps.payments.models.choices import (
            CREDIT_MOVEMENT_APPLIED,
            PAYMENT_CONFIRMED_STATUSES,
        )

        confirmed_payments_exists = Payment.objects.filter(
            id_invoice=invoice,
            status__in=PAYMENT_CONFIRMED_STATUSES,
        ).exists()

        confirmed_allocations_exists = PaymentAllocation.objects.filter(
            id_invoice=invoice,
            id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
        ).exists()

        confirmed_credit_exists = ClientCreditMovement.objects.filter(
            id_invoice=invoice,
            movement_type=CREDIT_MOVEMENT_APPLIED,
        ).exists()

        if confirmed_payments_exists or confirmed_allocations_exists or confirmed_credit_exists:
            raise ValueError("This invoice cannot be voided because it already has confirmed payments or credit applied.")

    except ValueError:
        raise
    except Exception:
        pass

    return True


@transaction.atomic
def void_invoice(invoice, user=None, reason=""):
    ensure_invoice_can_be_voided(invoice)
    ensure_invoice_has_no_confirmed_payments(invoice)

    invoice.status = INVOICE_STATUS_VOID
    invoice.voided_at = timezone.now()
    invoice.void_reason = (reason or "").strip()
    invoice.balance_due = Decimal("0.00")
    invoice.balance = Decimal("0.00")
    invoice.payment_status = INVOICE_PAYMENT_STATUS_VOID

    if user and user.is_authenticated:
        invoice.voided_by = user
        invoice.updated_by = user

    invoice.full_clean()
    invoice.save(
        update_fields=[
            "status",
            "voided_at",
            "voided_by",
            "void_reason",
            "balance_due",
            "balance",
            "payment_status",
            "updated_by",
            "last_modified_at",
        ]
    )

    try:
        from apps.payments.services import create_void_financial_movement

        create_void_financial_movement(invoice=invoice, user=user)
    except Exception:
        pass

    sync_related_project_invoice_status(invoice.id_project)

    return invoice




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
PDF_DANGER_LIGHT = colors.HexColor("#FDECEC")
PDF_SUCCESS = colors.HexColor("#0F766E")
PDF_SUCCESS_LIGHT = colors.HexColor("#E8F3EE")
PDF_WARNING = colors.HexColor("#B45309")
PDF_WARNING_LIGHT = colors.HexColor("#FFF3E2")


def get_invoice_pdf_filename(invoice: Invoice):
    base_name = invoice.invoice_number or f"invoice-{invoice.id_invoice}"
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


def _status_label(invoice):
    if invoice.status == INVOICE_STATUS_VOID:
        return "VOID"
    payment_status = _safe_text(getattr(invoice, "payment_status", ""), "").lower()
    if payment_status == INVOICE_PAYMENT_STATUS_PAID or money(getattr(invoice, "balance_due", 0)) == Decimal("0.00") and money(getattr(invoice, "paid_amount", 0)) > Decimal("0.00"):
        return "PAID"
    if payment_status == INVOICE_PAYMENT_STATUS_PARTIAL or money(getattr(invoice, "paid_amount", 0)) > Decimal("0.00"):
        return "PARTIAL"
    return _safe_text(getattr(invoice, "status", ""), "INVOICE").replace("_", " ").upper()


def _status_color(invoice):
    label = _status_label(invoice)
    if label == "VOID":
        return PDF_DANGER
    if label == "PAID":
        return PDF_SUCCESS
    if label == "PARTIAL":
        return PDF_ACCENT_DARK
    return PDF_PRIMARY


def _draw_page_footer(pdf):
    pdf.setStrokeColor(PDF_BORDER)
    pdf.setLineWidth(0.6)
    pdf.line(PDF_MARGIN, 45, PDF_WIDTH - PDF_MARGIN, 45)
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(PDF_MARGIN, 29, ui("Thank you for your business"))
    pdf.drawRightString(PDF_WIDTH - PDF_MARGIN, 29, f"{ui('Page')} {pdf.getPageNumber()}")


def _draw_document_stamp(pdf, label, color):
    if label not in ["VOID", "PAID", "PARTIAL"]:
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
    pdf.roundRect(-58, -17, 116, 34, 10, fill=1, stroke=1)
    pdf.setFillColor(color)
    pdf.setFont("Helvetica-Bold", 20)
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


def _draw_invoice_header(pdf, invoice):
    company = invoice.id_company
    use_dark_logo_background = bool(getattr(invoice, "pdf_header_dark", False))
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
    pdf.roundRect(PDF_WIDTH - 178, card_y + 12, 118, card_h - 24, 14, fill=1, stroke=0)

    _draw_logo(pdf, company, PDF_MARGIN + 14, PDF_HEIGHT - 91, use_dark=use_dark_logo_background)

    company_x = PDF_MARGIN + 128
    max_company_width = PDF_WIDTH - PDF_MARGIN * 2 - 300
    company_name = _safe_text(getattr(company, "name", None), "Company")
    while stringWidth(company_name, "Helvetica-Bold", 15) > max_company_width and len(company_name) > 16:
        company_name = company_name[:-2]
    if company_name != _safe_text(getattr(company, "name", None), "Company"):
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
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawRightString(right_x, PDF_HEIGHT - 43, ui("Invoice").upper())
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(right_x, PDF_HEIGHT - 62, _safe_text(invoice.invoice_number or invoice.id_invoice))
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(right_x, PDF_HEIGHT - 77, f"{ui('Issue Date')}: {_date_text(invoice.issue_date)}")
    pdf.drawRightString(right_x, PDF_HEIGHT - 91, f"{ui('Due Date')}: {_date_text(invoice.due_date)}")

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


def _invoice_items(invoice):
    if invoice.items.exists():
        return [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total": item.total,
            }
            for item in invoice.items.all()
        ]

    return invoice.detail_items or []


def _draw_invoice_items_table(pdf, invoice, y):
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
    pdf.drawString(left, y, ui("Items & Services"))
    pdf.setFillColor(PDF_MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(PDF_WIDTH - PDF_MARGIN, y, ui("All amounts are shown in USD"))
    y -= 15
    y = draw_table_header(y)

    items = _invoice_items(invoice)

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
        wrapped_description = _wrap_text(description, description_width - 18, "Helvetica", 8.5)
        row_height = max(26, 11 * len(wrapped_description) + 12)

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

        pdf.setFont("Helvetica", 8.5)
        text_y = y - 14
        for line in wrapped_description:
            pdf.drawString(left + number_width + 10, text_y, line[:120])
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


def _draw_invoice_totals(pdf, invoice, y):
    box_width = 245
    x = PDF_WIDTH - PDF_MARGIN - box_width
    rows = [
        (ui("Subtotal"), _money_text(invoice.subtotal), False, None),
        (ui("Discount"), _money_text(invoice.discount_amount), False, None),
        (ui("Tax"), _money_text(invoice.tax), False, None),
        (ui("Total"), _money_text(invoice.total), True, PDF_PRIMARY),
    ]

    if y < 210:
        _draw_page_footer(pdf)
        pdf.showPage()
        y = PDF_HEIGHT - 70

    row_height = 26
    total_height = row_height * len(rows) + 14
    _draw_shadow_card(pdf, x, y - total_height, box_width, total_height, fill_color=colors.white, radius=14)

    pdf.setFillColor(PDF_PRIMARY)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 14, y - 18, ui("Summary"))

    row_top = y - 31
    for index, (label, value, is_emphasis, fill_color) in enumerate(rows):
        row_y = row_top - (row_height * (index + 1))
        if is_emphasis:
            pdf.setFillColor(fill_color or PDF_PRIMARY)
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
    pdf.setFillColor(PDF_MUTED)
    y_text = y - 35
    _draw_wrapped_text(pdf, text, x + 14, y_text, width - 28, line_height=10.5, font_name="Helvetica", font_size=8.2, color=PDF_MUTED)
    return y - height - 12


def _build_invoice_pdf_bytes(invoice: Invoice):
    recalculate_invoice(invoice)
    ensure_invoice_can_download_pdf(invoice)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"{ui('Invoice')} {invoice.invoice_number or invoice.id_invoice}")

    y = _draw_invoice_header(pdf, invoice)
    left_x = PDF_MARGIN
    gap = 16
    card_width = (PDF_WIDTH - PDF_MARGIN * 2 - gap) / 2
    card_height = 126
    right_x = left_x + card_width + gap

    client_name = invoice.client_billing_name or getattr(invoice.id_client, "name", "")
    billing_email = invoice.client_billing_email or getattr(invoice.id_client, "email", "")
    billing_phone = invoice.client_billing_phone or getattr(invoice.id_client, "phone", "")
    billing_dni = invoice.client_billing_dni or getattr(invoice.id_client, "dni", "")
    billing_address = invoice.client_billing_address or getattr(invoice.id_client, "address", "")
    project_name = invoice.project_name or get_project_name(invoice.id_project)
    project_address = invoice.project_address or get_project_address(invoice.id_project)

    _draw_info_card(
        pdf,
        ui("Bill To"),
        [
            (ui("Client"), client_name),
            (ui("Email"), billing_email),
            (ui("Phone"), billing_phone),
            ("DNI / Tax ID", billing_dni),
            (ui("Address"), billing_address),
        ],
        left_x,
        y,
        card_width,
        card_height,
    )

    _draw_info_card(
        pdf,
        ui("Project"),
        [
            (ui("Project"), project_name),
            (ui("Location"), project_address),
            (ui("Invoice Date"), _date_text(invoice.issue_date)),
            (ui("Due Date"), _date_text(invoice.due_date)),
        ],
        right_x,
        y,
        card_width,
        card_height,
    )

    y = y - card_height - 26

    if invoice.description:
        desc_height = 58
        _draw_notes_terms(pdf, ui("Scope / Description"), invoice.description, PDF_MARGIN, y, PDF_WIDTH - PDF_MARGIN * 2, desc_height)
        y -= desc_height + 22

    if y < 180:
        _draw_page_footer(pdf)
        pdf.showPage()
        y = PDF_HEIGHT - 60

    y = _draw_invoice_items_table(pdf, invoice, y)
    totals_y = _draw_invoice_totals(pdf, invoice, y)

    notes_text = invoice.notes or ui("Payment is due according to the invoice terms. Please contact us if you have any questions about this invoice.")
    if totals_y > 130:
        _draw_notes_terms(pdf, ui("Notes / Terms"), notes_text, PDF_MARGIN, totals_y, PDF_WIDTH - PDF_MARGIN * 2 - 265, 88)
    else:
        _draw_notes_terms(pdf, ui("Notes / Terms"), notes_text, PDF_MARGIN, y, PDF_WIDTH - PDF_MARGIN * 2, 88)

    _draw_page_footer(pdf)
    pdf.save()
    return buffer.getvalue()


def build_invoice_pdf_bytes(invoice: Invoice):
    with company_language(invoice):
        return _build_invoice_pdf_bytes(invoice)


def invoice_pdf_response(invoice: Invoice):
    response = HttpResponse(build_invoice_pdf_bytes(invoice), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{get_invoice_pdf_filename(invoice)}"'
    return response

def create_invoices(**data):
    invoice = Invoice.objects.create(**data)
    recalculate_invoice(invoice)
    return invoice


def update_invoices(instance, **data):
    for field, value in data.items():
        setattr(instance, field, value)

    instance.save()
    recalculate_invoice(instance)
    return instance