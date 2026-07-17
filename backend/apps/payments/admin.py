from django.contrib import admin

from .models import (
    ClientCreditAccount,
    ClientCreditMovement,
    FinancialMovement,
    Payment,
    PaymentAllocation,
)
from .services import (
    generate_payment_number,
    generate_voucher_code,
    recalculate_invoice_payment_status,
)


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = (
        "id_invoice",
        "id_project",
        "amount",
        "allocated_at",
        "created_by",
    )
    readonly_fields = (
        "allocated_at",
        "created_by",
    )


class ClientCreditMovementInline(admin.TabularInline):
    model = ClientCreditMovement
    extra = 0
    fields = (
        "movement_type",
        "id_invoice",
        "amount",
        "balance_after",
        "description",
        "movement_date",
        "created_by",
    )
    readonly_fields = (
        "balance_after",
        "created_by",
        "created_at",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id_payment",
        "payment_number",
        "voucher_code",
        "reference_code",
        "id_company",
        "id_client",
        "main_invoice_display",
        "amount",
        "allocated_amount_display",
        "available_amount_display",
        "payment_method",
        "status",
        "payment_date",
        "verified_by",
        "verified_at",
        "voided_at",
    )

    search_fields = (
        "payment_number",
        "voucher_code",
        "reference_code",
        "id_company__name",
        "id_client__name",
        "id_invoice__invoice_number",
        "id_invoice__id_client__name",
        "allocations__id_invoice__invoice_number",
        "allocations__id_invoice__id_client__name",
        "payment_method",
        "notes",
    )

    list_filter = (
        "status",
        "payment_method",
        "payment_date",
        "id_company",
        "verified_at",
        "voided_at",
    )

    readonly_fields = (
        "payment_number",
        "allocated_amount_display",
        "available_amount_display",
        "created_at",
        "updated_at",
        "verified_by",
        "verified_at",
        "voided_by",
        "voided_at",
    )

    inlines = [
        PaymentAllocationInline,
        ClientCreditMovementInline,
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "id_company",
                "id_client",
                "id_invoice",
                "id_project",
                "verified_by",
                "voided_by",
                "created_by",
            )
            .prefetch_related(
                "allocations",
                "allocations__id_invoice",
                "credit_movements",
            )
        )

    def main_invoice_display(self, obj):
        if obj.id_invoice:
            return obj.id_invoice.invoice_number or obj.id_invoice.id_invoice

        if obj.allocations.exists():
            return "Multiple invoices"

        return "Credit only / no invoice"

    main_invoice_display.short_description = "Main Invoice"

    def allocated_amount_display(self, obj):
        return obj.allocated_amount

    allocated_amount_display.short_description = "Allocated"

    def available_amount_display(self, obj):
        return obj.available_amount

    available_amount_display.short_description = "Available"

    def save_model(self, request, obj, form, change):
        if obj.id_invoice:
            obj.id_company = obj.id_invoice.id_company
            obj.id_client = obj.id_invoice.id_client

            if obj.id_invoice.id_project:
                obj.id_project = obj.id_invoice.id_project

        if obj.id_client and not obj.id_company:
            obj.id_company = obj.id_client.id_company

        if obj.id_company and not obj.payment_number:
            obj.payment_number = generate_payment_number(obj.id_company)

        if not obj.voucher_code:
            obj.voucher_code = generate_voucher_code()

        if not obj.reference_code:
            obj.reference_code = obj.voucher_code

        if not obj.created_by:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        if obj.id_invoice:
            recalculate_invoice_payment_status(obj.id_invoice)

        for allocation in obj.allocations.select_related("id_invoice").all():
            recalculate_invoice_payment_status(allocation.id_invoice)


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "id_payment_allocation",
        "id_payment",
        "id_invoice",
        "id_company",
        "id_client",
        "id_project",
        "amount",
        "allocated_at",
        "created_by",
    )

    search_fields = (
        "id_payment__payment_number",
        "id_payment__voucher_code",
        "id_invoice__invoice_number",
        "id_client__name",
        "id_company__name",
        "id_project__name",
    )

    list_filter = (
        "id_company",
        "allocated_at",
    )

    readonly_fields = (
        "allocated_at",
        "created_at",
    )

    def save_model(self, request, obj, form, change):
        if obj.id_payment:
            obj.id_company = obj.id_payment.id_company
            obj.id_client = obj.id_payment.id_client

        if obj.id_invoice:
            obj.id_project = obj.id_invoice.id_project

        if not obj.created_by:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        if obj.id_invoice:
            recalculate_invoice_payment_status(obj.id_invoice)


@admin.register(ClientCreditAccount)
class ClientCreditAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id_credit_account",
        "id_company",
        "id_client",
        "balance",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "id_company__name",
        "id_client__name",
    )

    list_filter = (
        "id_company",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(ClientCreditMovement)
class ClientCreditMovementAdmin(admin.ModelAdmin):
    list_display = (
        "id_credit_movement",
        "movement_type",
        "id_company",
        "id_client",
        "id_payment",
        "id_invoice",
        "amount",
        "balance_after",
        "movement_date",
        "created_by",
    )

    search_fields = (
        "description",
        "id_company__name",
        "id_client__name",
        "id_payment__payment_number",
        "id_payment__voucher_code",
        "id_invoice__invoice_number",
    )

    list_filter = (
        "movement_type",
        "id_company",
        "movement_date",
    )

    readonly_fields = (
        "balance_after",
        "created_at",
    )


@admin.register(FinancialMovement)
class FinancialMovementAdmin(admin.ModelAdmin):
    list_display = (
        "id_financial_movement",
        "movement_type",
        "id_company",
        "id_client",
        "id_project",
        "id_invoice",
        "id_payment",
        "debit_amount",
        "credit_amount",
        "balance_after",
        "movement_date",
        "created_by",
    )

    search_fields = (
        "description",
        "id_company__name",
        "id_client__name",
        "id_invoice__invoice_number",
        "id_payment__payment_number",
        "id_payment__voucher_code",
    )

    list_filter = (
        "movement_type",
        "movement_date",
        "id_company",
    )

    readonly_fields = (
        "created_at",
    )