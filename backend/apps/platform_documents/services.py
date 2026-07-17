from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PlatformDocument, PlatformDocumentItem
from .models.choices import (
    DOCUMENT_STATUS_PAID,
    DOCUMENT_STATUS_SENT,
    DOCUMENT_TYPE_INVOICE,
    DOCUMENT_TYPE_PROFORMA,
)


def generate_platform_document_number(document_type):
    prefix = "INV" if document_type == DOCUMENT_TYPE_INVOICE else "PRO"
    year = timezone.localdate().year

    last_document = (
        PlatformDocument.objects.filter(
            document_number__startswith=f"{prefix}-{year}-"
        )
        .order_by("-id_document")
        .first()
    )

    if not last_document:
        next_number = 1
    else:
        try:
            next_number = int(last_document.document_number.split("-")[-1]) + 1
        except Exception:
            next_number = last_document.id_document + 1

    return f"{prefix}-{year}-{next_number:05d}"


def recalculate_platform_document(document):
    subtotal = Decimal("0.00")

    for item in document.items.all():
        item.subtotal = Decimal(str(item.quantity or 0)) * Decimal(str(item.unit_price or 0))
        item.save(update_fields=["subtotal"])
        subtotal += item.subtotal

    tax_rate = Decimal(str(document.tax_rate or 0))
    discount_amount = Decimal(str(document.discount_amount or 0))

    tax_amount = subtotal * (tax_rate / Decimal("100.00"))
    total = subtotal + tax_amount - discount_amount

    if total < 0:
        total = Decimal("0.00")

    document.subtotal = subtotal
    document.tax_amount = tax_amount
    document.total = total
    document.save(update_fields=["subtotal", "tax_amount", "total", "updated_at"])

    return document


def get_generated_invoice_for_proforma(proforma):
    if not proforma:
        return None

    return (
        PlatformDocument.objects.filter(
            source_document=proforma,
            document_type=DOCUMENT_TYPE_INVOICE,
        )
        .order_by("-id_document")
        .first()
    )


def can_generate_invoice_from_proforma(proforma):
    if not proforma:
        return False

    if proforma.document_type != DOCUMENT_TYPE_PROFORMA:
        return False

    if proforma.status != DOCUMENT_STATUS_PAID:
        return False

    if get_generated_invoice_for_proforma(proforma):
        return False

    return True


def generate_invoice_from_paid_proforma(proforma, created_by=None):
    if not can_generate_invoice_from_proforma(proforma):
        raise ValidationError(
            "Invoice can only be generated from a paid proforma without an existing invoice."
        )

    invoice = PlatformDocument.objects.create(
        id_company=proforma.id_company,
        id_subscription=proforma.id_subscription,
        source_document=proforma,
        document_number=generate_platform_document_number(DOCUMENT_TYPE_INVOICE),
        document_type=DOCUMENT_TYPE_INVOICE,
        status=DOCUMENT_STATUS_PAID,
        issue_date=timezone.localdate(),
        due_date=timezone.localdate(),
        tax_rate=proforma.tax_rate,
        discount_amount=proforma.discount_amount,
        notes=proforma.notes,
        terms=proforma.terms,
        footer=proforma.footer,
        created_by=created_by,
    )

    for item in proforma.items.all():
        PlatformDocumentItem.objects.create(
            id_document=invoice,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )

    recalculate_platform_document(invoice)

    return invoice