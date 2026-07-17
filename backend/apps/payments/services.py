import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.invoices.models import Invoice
from apps.invoices.models.choices import (
    INVOICE_PAYABLE_STATUSES,
    INVOICE_PAYMENT_STATUS_OVERPAID,
    INVOICE_PAYMENT_STATUS_PAID,
    INVOICE_PAYMENT_STATUS_PARTIAL,
    INVOICE_PAYMENT_STATUS_UNPAID,
    INVOICE_PAYMENT_STATUS_VOID,
    INVOICE_STATUS_CANCELLED,
    INVOICE_STATUS_VOID,
)

from .models import (
    ClientCreditAccount,
    ClientCreditMovement,
    FinancialMovement,
    Payment,
    PaymentAllocation,
)
from .models.choices import (
    CREDIT_MOVEMENT_APPLIED,
    CREDIT_MOVEMENT_CREATED,
    CREDIT_MOVEMENT_VOIDED,
    FINANCIAL_MOVEMENT_CREDIT_APPLIED,
    FINANCIAL_MOVEMENT_CREDIT_CREATED,
    FINANCIAL_MOVEMENT_CREDIT_VOID,
    FINANCIAL_MOVEMENT_INVOICE,
    FINANCIAL_MOVEMENT_PAYMENT,
    FINANCIAL_MOVEMENT_PAYMENT_VOID,
    FINANCIAL_MOVEMENT_VOID,
    PAYMENT_CONFIRMED_STATUSES,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_CONFIRMED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING_PAYMENT,
    PAYMENT_STATUS_REJECTED,
    PAYMENT_STATUS_VERIFIED,
    PAYMENT_STATUS_VOID,
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

    return value.quantize(
        MONEY_QUANTIZE,
        rounding=ROUND_HALF_UP,
    )


def generate_voucher_code():
    today = timezone.now().strftime("%Y%m%d")

    while True:
        code = f"VCH-{today}-{uuid.uuid4().hex[:8].upper()}"

        exists = Payment.objects.filter(
            voucher_code=code,
        ).exclude(
            status=PAYMENT_STATUS_VOID,
        ).exists()

        if not exists:
            return code


def generate_payment_number(company):
    last_payment = (
        Payment.objects.filter(id_company=company)
        .exclude(payment_number__isnull=True)
        .exclude(payment_number="")
        .order_by("-id_payment")
        .first()
    )

    if not last_payment or not last_payment.payment_number:
        return "PAY-000001"

    try:
        last_number = int(str(last_payment.payment_number).replace("PAY-", ""))
    except (TypeError, ValueError):
        last_number = last_payment.id_payment or 0

    return f"PAY-{last_number + 1:06d}"


def get_or_create_credit_account(company, client):
    account, _created = ClientCreditAccount.objects.get_or_create(
        id_company=company,
        id_client=client,
        defaults={
            "balance": Decimal("0.00"),
        },
    )

    return account


def get_credit_account_balance(company, client):
    account = get_or_create_credit_account(company, client)
    return money(account.balance)


def get_confirmed_allocation_total(invoice):
    total = (
        PaymentAllocation.objects.filter(
            id_invoice=invoice,
            id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return money(total)


def get_confirmed_legacy_payment_total(invoice):
    total = (
        Payment.objects.filter(
            id_invoice=invoice,
            status__in=PAYMENT_CONFIRMED_STATUSES,
            allocations__isnull=True,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return money(total)


def get_confirmed_credit_applied_total(invoice):
    total = (
        ClientCreditMovement.objects.filter(
            id_invoice=invoice,
            movement_type=CREDIT_MOVEMENT_APPLIED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    voided_total = (
        ClientCreditMovement.objects.filter(
            id_invoice=invoice,
            movement_type=CREDIT_MOVEMENT_VOIDED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return money(total - voided_total)


def get_confirmed_payment_total(invoice):
    total = Decimal("0.00")
    total += get_confirmed_allocation_total(invoice)
    total += get_confirmed_legacy_payment_total(invoice)
    total += get_confirmed_credit_applied_total(invoice)

    return money(total)


def get_client_current_balance(company, client, project=None):
    invoices = Invoice.objects.filter(
        id_company=company,
        id_client=client,
    ).exclude(
        status__in=[
            INVOICE_STATUS_VOID,
            INVOICE_STATUS_CANCELLED,
        ]
    )

    if project:
        invoices = invoices.filter(id_project=project)

    balance = Decimal("0.00")

    for invoice in invoices:
        balance += invoice.balance_due or Decimal("0.00")

    return money(balance)


@transaction.atomic
def recalculate_invoice_payment_status(invoice):
    paid_amount = get_confirmed_payment_total(invoice)

    if invoice.status in [
        INVOICE_STATUS_VOID,
        INVOICE_STATUS_CANCELLED,
    ]:
        invoice.paid_amount = money(paid_amount)
        invoice.balance_due = Decimal("0.00")
        invoice.balance = Decimal("0.00")
        invoice.payment_status = INVOICE_PAYMENT_STATUS_VOID

        invoice.save(
            update_fields=[
                "paid_amount",
                "balance_due",
                "balance",
                "payment_status",
                "last_modified_at",
            ]
        )

        return invoice

    total = money(invoice.total)
    balance_due = money(total - paid_amount)

    if balance_due < Decimal("0.00"):
        balance_due = Decimal("0.00")

    if paid_amount == Decimal("0.00"):
        payment_status = INVOICE_PAYMENT_STATUS_UNPAID
    elif paid_amount < total:
        payment_status = INVOICE_PAYMENT_STATUS_PARTIAL
    elif paid_amount == total:
        payment_status = INVOICE_PAYMENT_STATUS_PAID
    else:
        payment_status = INVOICE_PAYMENT_STATUS_OVERPAID

    last_payment = (
        PaymentAllocation.objects.filter(
            id_invoice=invoice,
            id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
        )
        .select_related("id_payment")
        .order_by("-id_payment__payment_date", "-id_payment_id")
        .first()
    )

    invoice.paid_amount = money(paid_amount)
    invoice.balance_due = balance_due
    invoice.balance = balance_due
    invoice.payment_status = payment_status

    if last_payment:
        invoice.last_payment_at = timezone.now()

    invoice.save(
        update_fields=[
            "paid_amount",
            "balance_due",
            "balance",
            "payment_status",
            "last_payment_at",
            "last_modified_at",
        ]
    )

    return invoice


def ensure_invoice_can_receive_payment(invoice):
    if invoice.status not in INVOICE_PAYABLE_STATUSES:
        raise ValueError("Only generated or sent invoices can receive payments.")

    recalculate_invoice_payment_status(invoice)

    if invoice.balance_due <= Decimal("0.00"):
        raise ValueError("This invoice does not have pending balance.")

    return True


def validate_payment_amount(payment):
    if payment.amount is None:
        raise ValueError("Payment amount is required.")

    payment.amount = money(payment.amount)

    if payment.amount < Decimal("0.00"):
        raise ValueError("Payment amount cannot be negative.")

    return True


def validate_payment_voucher(payment):
    if not payment.voucher_code:
        payment.voucher_code = generate_voucher_code()

    exists = Payment.objects.filter(
        id_company=payment.id_company,
        voucher_code=payment.voucher_code,
    ).exclude(
        status=PAYMENT_STATUS_VOID,
    )

    if payment.pk:
        exists = exists.exclude(pk=payment.pk)

    if exists.exists():
        raise ValueError(
            "This voucher code already exists for this company. You can only reuse it if the previous payment is void."
        )

    return True


def validate_payment_reference(payment):
    if not payment.reference_code:
        payment.reference_code = payment.voucher_code

    if not payment.reference_code:
        raise ValueError("Reference code is required.")

    exists = Payment.objects.filter(
        id_company=payment.id_company,
        reference_code=payment.reference_code,
    ).exclude(
        status=PAYMENT_STATUS_VOID,
    )

    if payment.pk:
        exists = exists.exclude(pk=payment.pk)

    if exists.exists():
        raise ValueError(
            "This payment reference code already exists for this company. You can only reuse it if the previous payment is void."
        )

    return True


def sync_payment_relations(payment):
    if payment.id_invoice:
        payment.id_company = payment.id_invoice.id_company
        payment.id_client = payment.id_invoice.id_client

        if payment.id_invoice.id_project:
            payment.id_project = payment.id_invoice.id_project

    if not payment.id_company:
        raise ValueError("Payment company is required.")

    if not payment.id_client:
        raise ValueError("Payment client is required.")

    return payment


def normalize_allocation_data(payment, allocations_data=None, fallback_invoice=None):
    normalized = []

    if allocations_data is not None:
        for item in allocations_data:
            invoice = item.get("invoice") or item.get("id_invoice")
            amount = money(item.get("amount"))

            if not invoice:
                continue

            if not isinstance(invoice, Invoice):
                invoice = Invoice.objects.get(id_invoice=invoice)

            if amount <= Decimal("0.00"):
                continue

            normalized.append(
                {
                    "invoice": invoice,
                    "amount": amount,
                }
            )

        return normalized

    invoice = fallback_invoice or payment.id_invoice

    if invoice:
        recalculate_invoice_payment_status(invoice)

        allocation_amount = min(
            money(payment.amount),
            money(invoice.balance_due),
        )

        if allocation_amount > Decimal("0.00"):
            normalized.append(
                {
                    "invoice": invoice,
                    "amount": allocation_amount,
                }
            )

    return normalized

def validate_allocation(payment, invoice, amount, running_total):
    if invoice.id_company_id != payment.id_company_id:
        raise ValueError("All allocated invoices must belong to the payment company.")

    if invoice.id_client_id != payment.id_client_id:
        raise ValueError("All allocated invoices must belong to the payment client.")

    ensure_invoice_can_receive_payment(invoice)

    if amount > invoice.balance_due:
        raise ValueError(
            f"Allocation amount for invoice {invoice.invoice_number or invoice.id_invoice} cannot be greater than its balance due."
        )

    if running_total + amount > payment.amount:
        raise ValueError("Total allocated amount cannot be greater than payment amount.")

    return True


@transaction.atomic
def clear_payment_allocations(payment):
    affected_invoices = list(
        Invoice.objects.filter(
            payment_allocations__id_payment=payment,
        ).distinct()
    )

    PaymentAllocation.objects.filter(
        id_payment=payment,
    ).delete()

    FinancialMovement.objects.filter(
        id_payment=payment,
        movement_type=FINANCIAL_MOVEMENT_PAYMENT,
    ).delete()

    for invoice in affected_invoices:
        recalculate_invoice_payment_status(invoice)

    return affected_invoices


@transaction.atomic
def create_payment_allocation(payment, invoice, amount, user=None):
    allocation, created = PaymentAllocation.objects.update_or_create(
        id_payment=payment,
        id_invoice=invoice,
        defaults={
            "id_company": payment.id_company,
            "id_client": payment.id_client,
            "id_project": invoice.id_project,
            "amount": money(amount),
            "created_by": user if user and user.is_authenticated else None,
        },
    )

    recalculate_invoice_payment_status(invoice)

    create_payment_financial_movement(
        payment=payment,
        invoice=invoice,
        amount=allocation.amount,
        user=user,
    )

    return allocation

@transaction.atomic
def create_or_update_credit_from_payment(payment, credit_amount, user=None):
    credit_amount = money(credit_amount)

    if credit_amount <= Decimal("0.00"):
        return None

    existing_credit = ClientCreditMovement.objects.filter(
        id_payment=payment,
        movement_type=CREDIT_MOVEMENT_CREATED,
    ).first()

    if existing_credit:
        return existing_credit

    account = get_or_create_credit_account(
        company=payment.id_company,
        client=payment.id_client,
    )

    account.balance = money(account.balance + credit_amount)
    account.updated_at = timezone.now()
    account.save(
        update_fields=[
            "balance",
            "updated_at",
        ]
    )

    movement = ClientCreditMovement.objects.create(
        id_company=payment.id_company,
        id_client=payment.id_client,
        id_payment=payment,
        movement_type=CREDIT_MOVEMENT_CREATED,
        amount=credit_amount,
        balance_after=account.balance,
        description=f"Credit created from payment {payment.payment_number or payment.voucher_code}",
        movement_date=payment.payment_date or timezone.localdate(),
        created_by=user if user and user.is_authenticated else None,
    )

    create_credit_financial_movement(
        company=payment.id_company,
        client=payment.id_client,
        payment=payment,
        invoice=None,
        movement_type=FINANCIAL_MOVEMENT_CREDIT_CREATED,
        amount=credit_amount,
        description=f"Credit balance created from payment {payment.payment_number or payment.voucher_code}",
        user=user,
    )

    return movement


@transaction.atomic
def replace_payment_allocations(payment, allocations_data=None, user=None, fallback_invoice=None):
    fallback_invoice = fallback_invoice or payment.id_invoice

    if payment.pk and payment.id_invoice_id:
        payment.id_invoice = None
        payment.updated_at = timezone.now()
        payment.save(
            update_fields=[
                "id_invoice",
                "updated_at",
            ]
        )

    clear_payment_allocations(payment)

    allocations = normalize_allocation_data(
        payment=payment,
        allocations_data=allocations_data,
        fallback_invoice=fallback_invoice,
    )

    running_total = Decimal("0.00")
    created_allocations = []
    first_invoice = None

    for item in allocations:
        invoice = item["invoice"]
        amount = money(item["amount"])

        validate_allocation(
            payment=payment,
            invoice=invoice,
            amount=amount,
            running_total=running_total,
        )

        allocation = create_payment_allocation(
            payment=payment,
            invoice=invoice,
            amount=amount,
            user=user,
        )

        created_allocations.append(allocation)
        running_total += amount

        if not first_invoice:
            first_invoice = invoice

    if first_invoice:
        payment.id_invoice = first_invoice
        payment.id_project = first_invoice.id_project
        payment.updated_at = timezone.now()
        payment.save(
            update_fields=[
                "id_invoice",
                "id_project",
                "updated_at",
            ]
        )

    credit_amount = money(payment.amount - running_total)

    create_or_update_credit_from_payment(
        payment=payment,
        credit_amount=credit_amount,
        user=user,
    )

    return created_allocations

@transaction.atomic
def create_invoice_financial_movement(invoice, user=None):
    existing_movement = FinancialMovement.objects.filter(
        id_company=invoice.id_company,
        id_invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_INVOICE,
        id_payment__isnull=True,
    ).first()

    if existing_movement:
        return existing_movement

    balance_after = get_client_current_balance(
        company=invoice.id_company,
        client=invoice.id_client,
    )

    return FinancialMovement.objects.create(
        id_company=invoice.id_company,
        id_client=invoice.id_client,
        id_project=invoice.id_project,
        id_invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_INVOICE,
        movement_date=invoice.issue_date or timezone.localdate(),
        description=f"Invoice {invoice.invoice_number or invoice.id_invoice}",
        debit_amount=money(invoice.total),
        credit_amount=Decimal("0.00"),
        balance_after=balance_after,
        created_by=user if user and user.is_authenticated else None,
    )


@transaction.atomic
def create_payment_financial_movement(payment, invoice=None, amount=None, user=None):
    invoice = invoice or payment.id_invoice
    amount = money(amount if amount is not None else payment.amount)

    existing_movement = FinancialMovement.objects.filter(
        id_company=payment.id_company,
        id_payment=payment,
        id_invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_PAYMENT,
    ).first()

    if existing_movement:
        existing_movement.credit_amount = amount
        existing_movement.balance_after = get_client_current_balance(
            company=payment.id_company,
            client=payment.id_client,
        )
        existing_movement.save(
            update_fields=[
                "credit_amount",
                "balance_after",
            ]
        )

        return existing_movement

    balance_after = get_client_current_balance(
        company=payment.id_company,
        client=payment.id_client,
    )

    return FinancialMovement.objects.create(
        id_company=payment.id_company,
        id_client=payment.id_client,
        id_project=invoice.id_project if invoice else payment.id_project,
        id_invoice=invoice,
        id_payment=payment,
        movement_type=FINANCIAL_MOVEMENT_PAYMENT,
        movement_date=payment.payment_date or timezone.localdate(),
        description=(
            f"Payment {payment.payment_number or payment.voucher_code} "
            f"applied to invoice {invoice.invoice_number or invoice.id_invoice}"
            if invoice
            else f"Payment {payment.payment_number or payment.voucher_code}"
        ),
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
        balance_after=balance_after,
        created_by=user if user and user.is_authenticated else None,
    )


@transaction.atomic
def create_credit_financial_movement(
    company,
    client,
    payment=None,
    invoice=None,
    movement_type=FINANCIAL_MOVEMENT_CREDIT_CREATED,
    amount=Decimal("0.00"),
    description="",
    user=None,
):
    amount = money(amount)

    return FinancialMovement.objects.create(
        id_company=company,
        id_client=client,
        id_project=invoice.id_project if invoice else None,
        id_invoice=invoice,
        id_payment=payment,
        movement_type=movement_type,
        movement_date=timezone.localdate(),
        description=description,
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
        balance_after=get_client_current_balance(
            company=company,
            client=client,
        ),
        created_by=user if user and user.is_authenticated else None,
    )


@transaction.atomic
def create_void_financial_movement(invoice, user=None):
    existing_movement = FinancialMovement.objects.filter(
        id_company=invoice.id_company,
        id_invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_VOID,
        id_payment__isnull=True,
    ).first()

    if existing_movement:
        return existing_movement

    balance_after = get_client_current_balance(
        company=invoice.id_company,
        client=invoice.id_client,
    )

    return FinancialMovement.objects.create(
        id_company=invoice.id_company,
        id_client=invoice.id_client,
        id_project=invoice.id_project,
        id_invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_VOID,
        movement_date=timezone.localdate(),
        description=f"Void invoice {invoice.invoice_number or invoice.id_invoice}",
        debit_amount=Decimal("0.00"),
        credit_amount=money(invoice.total),
        balance_after=balance_after,
        created_by=user if user and user.is_authenticated else None,
    )


@transaction.atomic
def create_payment_void_financial_movement(payment, user=None):
    existing_movement = FinancialMovement.objects.filter(
        id_company=payment.id_company,
        id_payment=payment,
        movement_type=FINANCIAL_MOVEMENT_PAYMENT_VOID,
    ).first()

    if existing_movement:
        return existing_movement

    balance_after = get_client_current_balance(
        company=payment.id_company,
        client=payment.id_client,
    )

    return FinancialMovement.objects.create(
        id_company=payment.id_company,
        id_client=payment.id_client,
        id_project=payment.id_project,
        id_invoice=payment.id_invoice,
        id_payment=payment,
        movement_type=FINANCIAL_MOVEMENT_PAYMENT_VOID,
        movement_date=timezone.localdate(),
        description=f"Void payment {payment.payment_number or payment.voucher_code}",
        debit_amount=money(payment.amount),
        credit_amount=Decimal("0.00"),
        balance_after=balance_after,
        created_by=user if user and user.is_authenticated else None,
    )


@transaction.atomic
def finalize_payment(payment, user=None, status=PAYMENT_STATUS_CONFIRMED, allocations_data=None):
    fallback_invoice = payment.id_invoice

    sync_payment_relations(payment)
    validate_payment_amount(payment)

    if allocations_data is not None:
        payment.id_invoice = None

    if not payment.payment_number:
        payment.payment_number = generate_payment_number(payment.id_company)

    if not payment.voucher_code:
        payment.voucher_code = generate_voucher_code()

    if not payment.reference_code:
        payment.reference_code = payment.voucher_code

    validate_payment_voucher(payment)
    validate_payment_reference(payment)

    payment.status = status

    if user and user.is_authenticated:
        payment.created_by = payment.created_by or user

        if status in [
            PAYMENT_STATUS_VERIFIED,
            PAYMENT_STATUS_CONFIRMED,
        ]:
            payment.verified_by = user
            payment.verified_at = timezone.now()

    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save()

    if not payment.allocations.exists() or allocations_data is not None:
        replace_payment_allocations(
            payment=payment,
            allocations_data=allocations_data,
            user=user,
            fallback_invoice=None if allocations_data is not None else fallback_invoice,
        )

    affected_invoices = Invoice.objects.filter(
        payment_allocations__id_payment=payment,
    ).distinct()

    for invoice in affected_invoices:
        recalculate_invoice_payment_status(invoice)

    return payment

@transaction.atomic
def register_payment(payment, user=None, allow_overpayment=True, allocations_data=None):
    return finalize_payment(
        payment=payment,
        user=user,
        status=PAYMENT_STATUS_CONFIRMED,
        allocations_data=allocations_data,
    )


@transaction.atomic
def payment_create(**data):
    payment = Payment(**data)

    sync_payment_relations(payment)

    if not payment.payment_number:
        payment.payment_number = generate_payment_number(payment.id_company)

    if not payment.voucher_code:
        payment.voucher_code = generate_voucher_code()

    if not payment.reference_code:
        payment.reference_code = payment.voucher_code

    validate_payment_amount(payment)
    validate_payment_voucher(payment)
    validate_payment_reference(payment)

    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save()

    if payment.status in PAYMENT_CONFIRMED_STATUSES:
        replace_payment_allocations(payment=payment)

    return payment


@transaction.atomic
def payment_update(payment, **data):
    old_invoices = list(
        Invoice.objects.filter(
            payment_allocations__id_payment=payment,
        ).distinct()
    )

    if payment.id_invoice:
        old_invoices.append(payment.id_invoice)

    allowed_fields = [
        "id_invoice",
        "id_project",
        "id_client",
        "id_company",
        "amount",
        "payment_method",
        "receipt_file",
        "notes",
        "status",
        "reference_code",
        "voucher_code",
        "payment_date",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(payment, field, data[field])

    sync_payment_relations(payment)

    if not payment.payment_number:
        payment.payment_number = generate_payment_number(payment.id_company)

    if not payment.voucher_code:
        payment.voucher_code = generate_voucher_code()

    if not payment.reference_code:
        payment.reference_code = payment.voucher_code

    validate_payment_amount(payment)
    validate_payment_voucher(payment)
    validate_payment_reference(payment)

    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save()

    if payment.status in PAYMENT_CONFIRMED_STATUSES:
        replace_payment_allocations(payment=payment)

    for invoice in old_invoices:
        recalculate_invoice_payment_status(invoice)

    if payment.id_invoice:
        recalculate_invoice_payment_status(payment.id_invoice)

    return payment


@transaction.atomic
def payment_mark_pending(payment):
    payment.status = PAYMENT_STATUS_PENDING_PAYMENT
    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save(update_fields=["status", "updated_at"])

    for invoice in Invoice.objects.filter(payment_allocations__id_payment=payment).distinct():
        recalculate_invoice_payment_status(invoice)

    if payment.id_invoice:
        recalculate_invoice_payment_status(payment.id_invoice)

    return payment


@transaction.atomic
def payment_mark_paid(payment):
    return finalize_payment(
        payment=payment,
        status=PAYMENT_STATUS_PAID,
    )


@transaction.atomic
def payment_verify(payment, user):
    return finalize_payment(
        payment=payment,
        user=user,
        status=PAYMENT_STATUS_VERIFIED,
    )


@transaction.atomic
def payment_confirm(payment, user=None):
    return finalize_payment(
        payment=payment,
        user=user,
        status=PAYMENT_STATUS_CONFIRMED,
    )


@transaction.atomic
def payment_reject(payment):
    payment.status = PAYMENT_STATUS_REJECTED
    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save(update_fields=["status", "updated_at"])

    for invoice in Invoice.objects.filter(payment_allocations__id_payment=payment).distinct():
        recalculate_invoice_payment_status(invoice)

    if payment.id_invoice:
        recalculate_invoice_payment_status(payment.id_invoice)

    return payment


@transaction.atomic
def payment_cancel(payment):
    payment.status = PAYMENT_STATUS_CANCELLED
    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save(update_fields=["status", "updated_at"])

    for invoice in Invoice.objects.filter(payment_allocations__id_payment=payment).distinct():
        recalculate_invoice_payment_status(invoice)

    if payment.id_invoice:
        recalculate_invoice_payment_status(payment.id_invoice)

    return payment


def get_credit_created_by_payment(payment):
    total = (
        ClientCreditMovement.objects.filter(
            id_payment=payment,
            movement_type=CREDIT_MOVEMENT_CREATED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return money(total)


@transaction.atomic
def reverse_credit_created_by_payment(payment, user=None):
    credit_amount = get_credit_created_by_payment(payment)

    if credit_amount <= Decimal("0.00"):
        return None

    account = get_or_create_credit_account(
        company=payment.id_company,
        client=payment.id_client,
    )

    if account.balance < credit_amount:
        raise ValueError(
            "This payment cannot be voided because its credit balance was already used."
        )

    account.balance = money(account.balance - credit_amount)
    account.updated_at = timezone.now()
    account.save(
        update_fields=[
            "balance",
            "updated_at",
        ]
    )

    movement = ClientCreditMovement.objects.create(
        id_company=payment.id_company,
        id_client=payment.id_client,
        id_payment=payment,
        movement_type=CREDIT_MOVEMENT_VOIDED,
        amount=credit_amount,
        balance_after=account.balance,
        description=f"Credit voided from payment {payment.payment_number or payment.voucher_code}",
        movement_date=timezone.localdate(),
        created_by=user if user and user.is_authenticated else None,
    )

    create_credit_financial_movement(
        company=payment.id_company,
        client=payment.id_client,
        payment=payment,
        invoice=None,
        movement_type=FINANCIAL_MOVEMENT_CREDIT_VOID,
        amount=credit_amount,
        description=f"Credit balance voided from payment {payment.payment_number or payment.voucher_code}",
        user=user,
    )

    return movement


@transaction.atomic
def reverse_credit_applied_by_payment(payment, user=None):
    applied_movements = list(
        ClientCreditMovement.objects.select_related("id_invoice").filter(
            id_payment=payment,
            movement_type=CREDIT_MOVEMENT_APPLIED,
        )
    )

    if not applied_movements:
        return []

    reversed_movements = []
    account = get_or_create_credit_account(
        company=payment.id_company,
        client=payment.id_client,
    )

    for applied_movement in applied_movements:
        already_reversed = ClientCreditMovement.objects.filter(
            id_payment=payment,
            id_invoice=applied_movement.id_invoice,
            movement_type=CREDIT_MOVEMENT_VOIDED,
            description__icontains="Credit application reversed",
        ).exists()

        if already_reversed:
            continue

        amount = money(applied_movement.amount)

        if amount <= Decimal("0.00"):
            continue

        account.balance = money(account.balance + amount)
        account.updated_at = timezone.now()
        account.save(
            update_fields=[
                "balance",
                "updated_at",
            ]
        )

        reversed_movement = ClientCreditMovement.objects.create(
            id_company=payment.id_company,
            id_client=payment.id_client,
            id_payment=payment,
            id_invoice=applied_movement.id_invoice,
            movement_type=CREDIT_MOVEMENT_VOIDED,
            amount=amount,
            balance_after=account.balance,
            description=(
                f"Credit application reversed from payment "
                f"{payment.payment_number or payment.voucher_code}"
            ),
            movement_date=timezone.localdate(),
            created_by=user if user and user.is_authenticated else None,
        )

        create_credit_financial_movement(
            company=payment.id_company,
            client=payment.id_client,
            payment=payment,
            invoice=applied_movement.id_invoice,
            movement_type=FINANCIAL_MOVEMENT_CREDIT_VOID,
            amount=amount,
            description=(
                f"Credit application reversed from payment "
                f"{payment.payment_number or payment.voucher_code}"
            ),
            user=user,
        )

        if applied_movement.id_invoice:
            recalculate_invoice_payment_status(applied_movement.id_invoice)

        reversed_movements.append(reversed_movement)

    return reversed_movements


@transaction.atomic
def payment_void(payment, user=None, reason=""):
    if payment.status == PAYMENT_STATUS_VOID:
        return payment

    if payment.status not in PAYMENT_CONFIRMED_STATUSES:
        raise ValueError("Only paid, verified or confirmed payments can be voided.")

    sync_payment_relations(payment)

    affected_invoices = list(
        Invoice.objects.filter(
            payment_allocations__id_payment=payment,
        ).distinct()
    )

    credit_applied_invoices = list(
        Invoice.objects.filter(
            credit_movements__id_payment=payment,
            credit_movements__movement_type=CREDIT_MOVEMENT_APPLIED,
        ).distinct()
    )

    affected_invoices.extend(credit_applied_invoices)

    if payment.id_invoice:
        affected_invoices.append(payment.id_invoice)

    reverse_credit_applied_by_payment(
        payment=payment,
        user=user,
    )

    reverse_credit_created_by_payment(
        payment=payment,
        user=user,
    )

    payment.status = PAYMENT_STATUS_VOID
    payment.voided_at = timezone.now()
    payment.void_reason = (reason or "").strip()

    if user and user.is_authenticated:
        payment.voided_by = user

    payment.updated_at = timezone.now()
    payment.full_clean()
    payment.save(
        update_fields=[
            "status",
            "voided_at",
            "voided_by",
            "void_reason",
            "updated_at",
        ]
    )

    for invoice in affected_invoices:
        recalculate_invoice_payment_status(invoice)

    create_payment_void_financial_movement(
        payment=payment,
        user=user,
    )

    return payment


@transaction.atomic
def apply_client_credit_to_invoice(company, client, invoice, amount, user=None, payment=None):
    amount = money(amount)

    if amount <= Decimal("0.00"):
        raise ValueError("Credit amount must be greater than zero.")

    if invoice.id_company_id != company.id_company:
        raise ValueError("Invoice must belong to the selected company.")

    if invoice.id_client_id != client.id_client:
        raise ValueError("Invoice must belong to the selected client.")

    ensure_invoice_can_receive_payment(invoice)

    if amount > invoice.balance_due:
        raise ValueError("Credit amount cannot be greater than invoice balance due.")

    account = get_or_create_credit_account(
        company=company,
        client=client,
    )

    if account.balance < amount:
        raise ValueError("Client does not have enough credit balance.")

    account.balance = money(account.balance - amount)
    account.updated_at = timezone.now()
    account.save(
        update_fields=[
            "balance",
            "updated_at",
        ]
    )

    movement = ClientCreditMovement.objects.create(
        id_company=company,
        id_client=client,
        id_payment=payment,
        id_invoice=invoice,
        movement_type=CREDIT_MOVEMENT_APPLIED,
        amount=amount,
        balance_after=account.balance,
        description=f"Credit applied to invoice {invoice.invoice_number or invoice.id_invoice}",
        movement_date=timezone.localdate(),
        created_by=user if user and user.is_authenticated else None,
    )

    create_credit_financial_movement(
        company=company,
        client=client,
        payment=payment,
        invoice=invoice,
        movement_type=FINANCIAL_MOVEMENT_CREDIT_APPLIED,
        amount=amount,
        description=f"Credit applied to invoice {invoice.invoice_number or invoice.id_invoice}",
        user=user,
    )

    recalculate_invoice_payment_status(invoice)

    return movement


def create_payments(**data):
    return payment_create(**data)


def update_payments(instance, **data):
    return payment_update(instance, **data)