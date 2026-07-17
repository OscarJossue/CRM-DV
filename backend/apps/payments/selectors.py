from decimal import Decimal

from django.db.models import Q

from apps.clients.models import Client
from apps.invoices.models import Invoice
from apps.invoices.models.choices import (
    INVOICE_PAYMENT_STATUS_PAID,
    INVOICE_PAYMENT_STATUS_PARTIAL,
    INVOICE_PAYMENT_STATUS_UNPAID,
    INVOICE_PAYMENT_STATUS_VOID,
    INVOICE_STATUS_CANCELLED,
    INVOICE_STATUS_PENDING_SEND,
    INVOICE_STATUS_SENT,
    INVOICE_STATUS_VOID,
)
from apps.projects.models import Project

from .models import (
    ClientCreditAccount,
    ClientCreditMovement,
    FinancialMovement,
    Payment,
    PaymentAllocation,
)
from .models.choices import CREDIT_MOVEMENT_APPLIED, PAYMENT_CONFIRMED_STATUSES


def money(value):
    return value or Decimal("0.00")


def payment_list_for_user(user):
    queryset = (
        Payment.objects.select_related(
            "id_company",
            "id_client",
            "id_invoice",
            "id_invoice__id_company",
            "id_invoice__id_client",
            "id_project",
            "verified_by",
            "voided_by",
            "created_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__id_invoice",
            "allocations__id_project",
        )
        .all()
        .order_by(
            "-payment_date",
            "-id_payment",
        )
    )

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(
        Q(id_company_id=user.id_company_id)
        | Q(id_invoice__id_company_id=user.id_company_id)
        | Q(allocations__id_company_id=user.id_company_id)
    ).distinct()


def payment_get_for_user(user, id_payment):
    return payment_list_for_user(user).filter(
        id_payment=id_payment,
    ).first()


def list_payments(company=None):
    queryset = (
        Payment.objects.select_related(
            "id_company",
            "id_client",
            "id_invoice",
            "id_invoice__id_company",
            "id_invoice__id_client",
            "id_project",
            "verified_by",
            "voided_by",
            "created_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__id_invoice",
            "allocations__id_project",
        )
        .all()
        .order_by(
            "-payment_date",
            "-id_payment",
        )
    )

    if company:
        queryset = queryset.filter(
            Q(id_company=company)
            | Q(id_invoice__id_company=company)
            | Q(allocations__id_company=company)
        ).distinct()

    return queryset


def get_payments_by_id(pk):
    return Payment.objects.filter(pk=pk).first()


def get_payments_queryset(company):
    return (
        Payment.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_invoice",
            "created_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__id_invoice",
            "allocations__id_project",
        )
        .filter(
            Q(id_company=company)
            | Q(id_invoice__id_company=company)
            | Q(allocations__id_company=company)
        )
        .distinct()
    )


def get_payment_allocations_queryset(company):
    return PaymentAllocation.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_payment",
        "id_invoice",
        "created_by",
    ).filter(
        id_company=company,
    )


def get_credit_accounts_queryset(company):
    return ClientCreditAccount.objects.select_related(
        "id_company",
        "id_client",
    ).filter(
        id_company=company,
    )


def get_credit_movements_queryset(company):
    return ClientCreditMovement.objects.select_related(
        "id_company",
        "id_client",
        "id_payment",
        "id_invoice",
        "created_by",
    ).filter(
        id_company=company,
    )


def get_financial_movements_queryset(company):
    return FinancialMovement.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_invoice",
        "id_payment",
        "created_by",
    ).filter(
        id_company=company,
    )


def get_open_invoices_queryset(company):
    return Invoice.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
    ).filter(
        id_company=company,
        status__in=[
            INVOICE_STATUS_PENDING_SEND,
            INVOICE_STATUS_SENT,
        ],
        payment_status__in=[
            INVOICE_PAYMENT_STATUS_UNPAID,
            INVOICE_PAYMENT_STATUS_PARTIAL,
        ],
        balance_due__gt=0,
    )


def get_clients_with_open_balance(company):
    return Client.objects.filter(
        invoices__id_company=company,
        invoices__status__in=[
            INVOICE_STATUS_PENDING_SEND,
            INVOICE_STATUS_SENT,
        ],
        invoices__payment_status__in=[
            INVOICE_PAYMENT_STATUS_UNPAID,
            INVOICE_PAYMENT_STATUS_PARTIAL,
        ],
        invoices__balance_due__gt=0,
    ).distinct()


def get_projects_with_open_balance(company, client=None):
    queryset = Project.objects.filter(
        invoices__id_company=company,
        invoices__status__in=[
            INVOICE_STATUS_PENDING_SEND,
            INVOICE_STATUS_SENT,
        ],
        invoices__payment_status__in=[
            INVOICE_PAYMENT_STATUS_UNPAID,
            INVOICE_PAYMENT_STATUS_PARTIAL,
        ],
        invoices__balance_due__gt=0,
    )

    if client:
        queryset = queryset.filter(
            Q(id_client=client) | Q(invoices__id_client=client)
        )

    return queryset.distinct()


def get_open_invoices_for_client(company, client):
    return get_open_invoices_queryset(company).filter(
        id_client=client,
    )


def get_open_invoices_for_project(company, project):
    return get_open_invoices_queryset(company).filter(
        id_project=project,
    )


def get_all_financial_clients(company):
    return Client.objects.filter(
        Q(invoices__id_company=company)
        | Q(payments__id_company=company)
        | Q(payment_allocations__id_company=company)
        | Q(financial_movements__id_company=company)
        | Q(credit_accounts__id_company=company)
        | Q(credit_movements__id_company=company)
    ).distinct()


def get_client_credit_account(company, client):
    account = ClientCreditAccount.objects.filter(
        id_company=company,
        id_client=client,
    ).first()

    return account


def get_client_credit_balance(company, client):
    account = get_client_credit_account(company, client)

    if not account:
        return Decimal("0.00")

    return money(account.balance)


def get_client_confirmed_payments_total(company, client):
    total = Decimal("0.00")

    payments = Payment.objects.filter(
        id_company=company,
        id_client=client,
        status__in=PAYMENT_CONFIRMED_STATUSES,
    )

    for payment in payments:
        total += money(payment.amount)

    return total


def get_client_allocated_payments_total(company, client):
    total = Decimal("0.00")

    allocations = PaymentAllocation.objects.filter(
        id_company=company,
        id_client=client,
        id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
    )

    for allocation in allocations:
        total += money(allocation.amount)

    return total




def get_client_credit_applied_total(company, client):
    total = Decimal("0.00")

    movements = ClientCreditMovement.objects.filter(
        id_company=company,
        id_client=client,
        movement_type=CREDIT_MOVEMENT_APPLIED,
    )

    for movement in movements:
        total += money(movement.amount)

    return total

def get_client_financial_summary(company, client):
    invoices = Invoice.objects.filter(
        id_company=company,
        id_client=client,
    )

    active_invoices = invoices.exclude(
        status__in=[
            INVOICE_STATUS_VOID,
            INVOICE_STATUS_CANCELLED,
        ]
    )

    confirmed_payments = Payment.objects.filter(
        id_company=company,
        id_client=client,
        status__in=PAYMENT_CONFIRMED_STATUSES,
    )

    total_invoiced = Decimal("0.00")
    total_paid = get_client_confirmed_payments_total(
        company=company,
        client=client,
    )
    total_allocated = get_client_allocated_payments_total(
        company=company,
        client=client,
    ) + get_client_credit_applied_total(
        company=company,
        client=client,
    )
    balance_due = Decimal("0.00")
    credit_balance = get_client_credit_balance(
        company=company,
        client=client,
    )
    open_invoices = 0
    paid_invoices = 0
    partial_invoices = 0
    unpaid_invoices = 0

    for invoice in active_invoices:
        try:
            from .services import recalculate_invoice_payment_status
            recalculate_invoice_payment_status(invoice)
            invoice.refresh_from_db()
        except Exception:
            pass

        total_invoiced += money(invoice.total)

        invoice_balance = money(invoice.balance_due)

        if invoice_balance > 0:
            balance_due += invoice_balance
            open_invoices += 1

        if invoice.payment_status == INVOICE_PAYMENT_STATUS_PAID:
            paid_invoices += 1

        if invoice.payment_status == INVOICE_PAYMENT_STATUS_PARTIAL:
            partial_invoices += 1

        if invoice.payment_status == INVOICE_PAYMENT_STATUS_UNPAID:
            unpaid_invoices += 1

    void_invoices = invoices.filter(
        Q(status=INVOICE_STATUS_VOID)
        | Q(payment_status=INVOICE_PAYMENT_STATUS_VOID)
    ).count()

    last_payment = confirmed_payments.order_by(
        "-payment_date",
        "-id_payment",
    ).first()

    return {
        "client": client,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_allocated": total_allocated,
        "balance_due": balance_due,
        "credit_balance": credit_balance,
        "open_invoices": open_invoices,
        "paid_invoices": paid_invoices,
        "partial_invoices": partial_invoices,
        "unpaid_invoices": unpaid_invoices,
        "void_invoices": void_invoices,
        "last_payment": last_payment,
        "last_payment_date": last_payment.payment_date if last_payment else None,
    }


def get_all_clients_financial_summaries(company):
    summaries = []

    clients = get_all_financial_clients(company).order_by("pk")

    for client in clients:
        summaries.append(
            get_client_financial_summary(
                company=company,
                client=client,
            )
        )

    summaries.sort(
        key=lambda item: (
            item["balance_due"],
            item["credit_balance"],
            item["total_invoiced"],
        ),
        reverse=True,
    )

    return summaries


def get_client_invoices(company, client):
    return Invoice.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_estimate",
    ).filter(
        id_company=company,
        id_client=client,
    ).order_by(
        "-issue_date",
        "-id_invoice",
    )


def get_client_payments(company, client):
    return (
        Payment.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_invoice",
            "created_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__id_invoice",
            "allocations__id_project",
        )
        .filter(
            id_company=company,
            id_client=client,
        )
        .order_by(
            "-payment_date",
            "-id_payment",
        )
    )


def get_client_payment_allocations(company, client):
    return PaymentAllocation.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_payment",
        "id_invoice",
    ).filter(
        id_company=company,
        id_client=client,
    ).order_by(
        "-allocated_at",
        "-id_payment_allocation",
    )


def get_client_credit_movements(company, client):
    return ClientCreditMovement.objects.select_related(
        "id_company",
        "id_client",
        "id_payment",
        "id_invoice",
        "created_by",
    ).filter(
        id_company=company,
        id_client=client,
    ).order_by(
        "-movement_date",
        "-id_credit_movement",
    )


def get_client_movements(company, client):
    return get_financial_movements_queryset(company).filter(
        id_client=client,
    ).order_by(
        "-movement_date",
        "-id_financial_movement",
    )


def get_client_financial_statement(company, client):
    return {
        "summary": get_client_financial_summary(
            company=company,
            client=client,
        ),
        "invoices": get_client_invoices(
            company=company,
            client=client,
        ),
        "payments": get_client_payments(
            company=company,
            client=client,
        ),
        "allocations": get_client_payment_allocations(
            company=company,
            client=client,
        ),
        "credit_movements": get_client_credit_movements(
            company=company,
            client=client,
        ),
        "movements": get_client_movements(
            company=company,
            client=client,
        ),
        "credit_account": get_client_credit_account(
            company=company,
            client=client,
        ),
    }