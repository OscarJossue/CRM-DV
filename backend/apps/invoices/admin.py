from django.contrib import admin

from .models import Invoice, InvoiceItem
from .services import generate_invoice_number, recalculate_invoice


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

    fields = (
        "description",
        "quantity",
        "unit_price",
        "taxable",
        "subtotal",
        "total",
    )

    readonly_fields = (
        "subtotal",
        "total",
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id_invoice",
        "invoice_number",
        "id_company",
        "id_client",
        "id_project",
        "id_estimate",
        "status",
        "payment_status",
        "subtotal",
        "tax",
        "discount_amount",
        "total",
        "paid_amount",
        "balance_due",
        "issue_date",
        "due_date",
    )

    search_fields = (
        "invoice_number",
        "id_company__name",
        "id_client__name",
        "id_project__name",
        "client_billing_name",
        "client_billing_dni",
        "client_billing_email",
        "project_name",
        "description",
        "void_reason",
    )

    list_filter = (
        "status",
        "payment_status",
        "issue_date",
        "due_date",
        "id_company",
        "generated_at",
        "sent_at",
        "voided_at",
    )

    readonly_fields = (
        "invoice_number",
        "subtotal",
        "tax",
        "total",
        "balance",
        "paid_amount",
        "balance_due",
        "created_at",
        "updated_at",
        "last_modified_at",
        "generated_at",
        "sent_at",
        "voided_at",
    )

    inlines = [InvoiceItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.invoice_number:
            obj.invoice_number = generate_invoice_number(obj.id_company)

        if not obj.created_by:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        recalculate_invoice(form.instance)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "description",
        "quantity",
        "unit_price",
        "taxable",
        "subtotal",
        "total",
    )

    list_filter = (
        "taxable",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "invoice__invoice_number",
        "description",
    )

    readonly_fields = (
        "subtotal",
        "total",
        "created_at",
        "updated_at",
    )