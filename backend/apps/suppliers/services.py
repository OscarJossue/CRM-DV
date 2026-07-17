from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction

from .models import Supplier, SupplierOffer, SupplierPurchase
from .models.choices import (
    OFFER_TYPE_PRODUCT,
    PURCHASE_PAYMENT_STATUS_PAID,
    PURCHASE_PAYMENT_STATUS_PARTIAL,
    PURCHASE_PAYMENT_STATUS_UNPAID,
    PURCHASE_STATUS_CANCELLED,
    SUPPLIER_STATUS_ACTIVE,
    SUPPLIER_STATUS_INACTIVE,
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


def _next_number(queryset, field_name, prefix):
    last_object = (
        queryset.exclude(**{f"{field_name}__isnull": True})
        .exclude(**{field_name: ""})
        .order_by("-pk")
        .first()
    )

    if not last_object:
        return f"{prefix}-000001"

    last_code = getattr(last_object, field_name, "") or ""

    try:
        last_number = int(str(last_code).replace(f"{prefix}-", ""))
    except (TypeError, ValueError):
        last_number = getattr(last_object, "pk", 0) or 0

    return f"{prefix}-{last_number + 1:06d}"


def generate_supplier_code(company):
    return _next_number(
        Supplier.objects.filter(id_company=company),
        "supplier_code",
        "SUP",
    )


def generate_purchase_number(company):
    return _next_number(
        SupplierPurchase.objects.filter(id_company=company),
        "purchase_number",
        "PUR",
    )


def get_purchase_payment_status(total, paid_amount):
    total = money(total)
    paid_amount = money(paid_amount)

    if paid_amount <= Decimal("0.00"):
        return PURCHASE_PAYMENT_STATUS_UNPAID

    if paid_amount < total:
        return PURCHASE_PAYMENT_STATUS_PARTIAL

    return PURCHASE_PAYMENT_STATUS_PAID


def recalculate_purchase(purchase, save=True):
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")

    for item in purchase.items.select_related("id_offer").all():
        if item.id_offer:
            item.item_name = item.item_name or item.id_offer.name
            item.description = item.description or item.id_offer.description or ""
            item.unit = item.unit or item.id_offer.unit or ""
        line_subtotal = money((item.quantity or Decimal("0.00")) * (item.unit_price or Decimal("0.00")))
        item.tax_amount = money(item.tax_amount)
        item.total = money(line_subtotal + item.tax_amount)
        item.save(update_fields=["item_name", "description", "unit", "tax_amount", "total", "updated_at"])
        subtotal += line_subtotal
        tax_amount += item.tax_amount

    purchase.subtotal = money(subtotal)
    purchase.tax_amount = money(tax_amount)
    purchase.discount_amount = money(purchase.discount_amount)

    total = purchase.subtotal + purchase.tax_amount - purchase.discount_amount
    if total < Decimal("0.00"):
        total = Decimal("0.00")

    purchase.total = money(total)
    purchase.paid_amount = money(purchase.paid_amount)

    if purchase.paid_amount > purchase.total:
        purchase.paid_amount = purchase.total

    balance_due = purchase.total - purchase.paid_amount
    if balance_due < Decimal("0.00"):
        balance_due = Decimal("0.00")

    purchase.balance_due = money(balance_due)
    purchase.payment_status = get_purchase_payment_status(purchase.total, purchase.paid_amount)

    if save:
        purchase.save(
            update_fields=[
                "subtotal",
                "tax_amount",
                "discount_amount",
                "total",
                "paid_amount",
                "balance_due",
                "payment_status",
                "updated_at",
            ]
        )

    return purchase


@transaction.atomic
def create_supplier_from_form(form, user):
    supplier = form.save(commit=False)
    supplier.id_company = user.id_company
    supplier.created_by = user
    supplier.updated_by = user

    if not supplier.supplier_code:
        supplier.supplier_code = generate_supplier_code(user.id_company)

    supplier.save()
    return supplier


@transaction.atomic
def update_supplier_from_form(form, user):
    supplier = form.save(commit=False)
    supplier.updated_by = user
    supplier.id_company = supplier.id_company or user.id_company

    if not supplier.supplier_code:
        supplier.supplier_code = generate_supplier_code(supplier.id_company)

    supplier.save()
    return supplier


def activate_supplier(supplier, user=None):
    supplier.status = SUPPLIER_STATUS_ACTIVE
    if user:
        supplier.updated_by = user
    supplier.save(update_fields=["status", "updated_by", "updated_at"])
    return supplier


def deactivate_supplier(supplier, user=None):
    supplier.status = SUPPLIER_STATUS_INACTIVE
    if user:
        supplier.updated_by = user
    supplier.save(update_fields=["status", "updated_by", "updated_at"])
    return supplier


@transaction.atomic
def delete_supplier_if_empty(supplier):
    if supplier.purchases.exists():
        return False
    supplier.delete()
    return True


def activate_product(product, user=None):
    product.status = SUPPLIER_STATUS_ACTIVE
    if user:
        product.updated_by = user
    product.save(update_fields=["status", "updated_by", "updated_at"])
    return product


def deactivate_product(product, user=None):
    product.status = SUPPLIER_STATUS_INACTIVE
    if user:
        product.updated_by = user
    product.save(update_fields=["status", "updated_by", "updated_at"])
    return product


@transaction.atomic
def delete_product_if_unused(product):
    if product.purchase_items.exists():
        return False
    product.delete()
    return True


@transaction.atomic
def create_product_from_form(form, user):
    product = form.save(commit=False)
    product.id_company = product.id_supplier.id_company
    product.offer_type = OFFER_TYPE_PRODUCT
    product.created_by = user
    product.updated_by = user
    product.save()
    return product


@transaction.atomic
def update_product_from_form(form, user):
    product = form.save(commit=False)
    product.id_company = product.id_supplier.id_company
    product.offer_type = OFFER_TYPE_PRODUCT
    product.updated_by = user
    product.save()
    return product


def _prepare_item(item, purchase):
    if item.id_offer and item.id_offer.id_supplier_id != purchase.id_supplier_id:
        raise ValueError("Selected product does not belong to this supplier.")
    if item.id_offer:
        item.item_name = item.id_offer.name
        if not item.description:
            item.description = item.id_offer.description or ""
        if not item.unit:
            item.unit = item.id_offer.unit or ""
    item.id_purchase = purchase
    item.total = money((item.quantity or Decimal("0.00")) * (item.unit_price or Decimal("0.00")) + (item.tax_amount or Decimal("0.00")))
    return item


@transaction.atomic
def create_purchase_with_items(form, formset, user):
    purchase = form.save(commit=False)
    purchase.id_company = user.id_company
    purchase.created_by = user
    purchase.updated_by = user

    if not purchase.purchase_number:
        purchase.purchase_number = generate_purchase_number(user.id_company)

    purchase.save()
    formset.instance = purchase
    items = formset.save(commit=False)

    for deleted_item in formset.deleted_objects:
        deleted_item.delete()

    for item in items:
        item = _prepare_item(item, purchase)
        item.save()

    recalculate_purchase(purchase)
    return purchase


@transaction.atomic
def update_purchase_with_items(form, formset, user):
    purchase = form.save(commit=False)
    purchase.updated_by = user
    purchase.save()
    formset.instance = purchase
    items = formset.save(commit=False)

    for deleted_item in formset.deleted_objects:
        deleted_item.delete()

    for item in items:
        item = _prepare_item(item, purchase)
        item.save()

    recalculate_purchase(purchase)
    return purchase


def cancel_purchase(purchase, user=None):
    purchase.status = PURCHASE_STATUS_CANCELLED
    if user:
        purchase.updated_by = user
    purchase.save(update_fields=["status", "updated_by", "updated_at"])
    return purchase
