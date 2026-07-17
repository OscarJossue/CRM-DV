from rest_framework import serializers

from .models import Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id_invoice_item",
            "description",
            "quantity",
            "unit_price",
            "taxable",
            "subtotal",
            "total",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_invoice", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    client_name = serializers.CharField(source="id_client.name", read_only=True)
    project_relation_name = serializers.CharField(
        source="id_project.name",
        read_only=True,
        allow_null=True,
    )
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "id_invoice",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_project",
            "project_relation_name",
            "id_estimate",
            "invoice_number",
            "detail_items",
            "client_billing_name",
            "client_billing_email",
            "client_billing_phone",
            "client_billing_dni",
            "client_billing_address",
            "project_name",
            "project_address",
            "description",
            "subtotal",
            "tax_enabled",
            "tax_rate",
            "tax",
            "discount_amount",
            "total",
            "balance",
            "paid_amount",
            "balance_due",
            "payment_status",
            "last_payment_at",
            "issue_date",
            "due_date",
            "status",
            "notes",
            "generated_at",
            "sent_at",
            "voided_at",
            "void_reason",
            "created_at",
            "updated_at",
            "last_modified_at",
            "items",
        ]

        read_only_fields = [
            "invoice_number",
            "subtotal",
            "tax",
            "total",
            "balance",
            "paid_amount",
            "balance_due",
            "payment_status",
            "last_payment_at",
            "generated_at",
            "sent_at",
            "voided_at",
            "created_at",
            "updated_at",
            "last_modified_at",
        ]