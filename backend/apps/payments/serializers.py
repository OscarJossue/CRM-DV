from rest_framework import serializers

from .models import (
    ClientCreditAccount,
    ClientCreditMovement,
    FinancialMovement,
    Payment,
    PaymentAllocation,
)


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAllocation
        fields = [
            "id_payment_allocation",
            "id_company",
            "id_client",
            "id_project",
            "project_name",
            "id_payment",
            "id_invoice",
            "invoice_number",
            "amount",
            "allocated_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id_payment_allocation",
            "id_company",
            "id_client",
            "id_project",
            "id_payment",
            "allocated_at",
            "created_by",
            "created_at",
        ]

    def get_invoice_number(self, obj):
        if obj.id_invoice:
            return obj.id_invoice.invoice_number or obj.id_invoice.id_invoice

        return None

    def get_project_name(self, obj):
        if obj.id_project:
            return obj.id_project.name

        if obj.id_invoice and obj.id_invoice.id_project:
            return obj.id_invoice.id_project.name

        return None


class ClientCreditAccountSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = ClientCreditAccount
        fields = [
            "id_credit_account",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id_credit_account",
            "created_at",
            "updated_at",
        ]

    def get_company_name(self, obj):
        return obj.id_company.name if obj.id_company else None

    def get_client_name(self, obj):
        return obj.id_client.name if obj.id_client else None


class ClientCreditMovementSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    payment_number = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = ClientCreditMovement
        fields = [
            "id_credit_movement",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_payment",
            "payment_number",
            "id_invoice",
            "invoice_number",
            "movement_type",
            "amount",
            "balance_after",
            "description",
            "movement_date",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id_credit_movement",
            "balance_after",
            "created_by",
            "created_at",
        ]

    def get_company_name(self, obj):
        return obj.id_company.name if obj.id_company else None

    def get_client_name(self, obj):
        return obj.id_client.name if obj.id_client else None

    def get_payment_number(self, obj):
        if obj.id_payment:
            return (
                obj.id_payment.payment_number
                or obj.id_payment.voucher_code
                or obj.id_payment.id_payment
            )

        return None

    def get_invoice_number(self, obj):
        if obj.id_invoice:
            return obj.id_invoice.invoice_number or obj.id_invoice.id_invoice

        return None


class FinancialMovementSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    payment_number = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = FinancialMovement
        fields = [
            "id_financial_movement",
            "movement_type",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_project",
            "project_name",
            "id_invoice",
            "invoice_number",
            "id_payment",
            "payment_number",
            "debit_amount",
            "credit_amount",
            "balance_after",
            "movement_date",
            "description",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id_financial_movement",
            "balance_after",
            "created_by",
            "created_at",
        ]

    def get_company_name(self, obj):
        return obj.id_company.name if obj.id_company else None

    def get_client_name(self, obj):
        return obj.id_client.name if obj.id_client else None

    def get_project_name(self, obj):
        return obj.id_project.name if obj.id_project else None

    def get_payment_number(self, obj):
        if obj.id_payment:
            return (
                obj.id_payment.payment_number
                or obj.id_payment.voucher_code
                or obj.id_payment.id_payment
            )

        return None

    def get_invoice_number(self, obj):
        if obj.id_invoice:
            return obj.id_invoice.invoice_number or obj.id_invoice.id_invoice

        return None


class PaymentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_payment", read_only=True)

    company_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    main_invoice_number = serializers.SerializerMethodField()
    verified_by_email = serializers.SerializerMethodField()

    allocated_amount = serializers.SerializerMethodField()
    available_amount = serializers.SerializerMethodField()

    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    credit_movements = ClientCreditMovementSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "id_payment",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_project",
            "project_name",
            "id_invoice",
            "main_invoice_number",
            "payment_number",
            "voucher_code",
            "reference_code",
            "amount",
            "allocated_amount",
            "available_amount",
            "payment_method",
            "receipt_file",
            "notes",
            "payment_date",
            "status",
            "verified_by",
            "verified_by_email",
            "verified_at",
            "voided_by",
            "voided_at",
            "void_reason",
            "created_by",
            "created_at",
            "updated_at",
            "allocations",
            "credit_movements",
        ]
        read_only_fields = [
            "id",
            "id_payment",
            "payment_number",
            "allocated_amount",
            "available_amount",
            "verified_by",
            "verified_at",
            "voided_by",
            "voided_at",
            "created_by",
            "created_at",
            "updated_at",
            "allocations",
            "credit_movements",
        ]

    def get_company_name(self, obj):
        if obj.id_company:
            return obj.id_company.name

        if obj.id_invoice:
            return obj.id_invoice.id_company.name

        return None

    def get_client_name(self, obj):
        if obj.id_client:
            return obj.id_client.name

        if obj.id_invoice:
            return obj.id_invoice.id_client.name

        return None

    def get_project_name(self, obj):
        if obj.id_project:
            return obj.id_project.name

        if obj.id_invoice and obj.id_invoice.id_project:
            return obj.id_invoice.id_project.name

        return None

    def get_main_invoice_number(self, obj):
        if obj.id_invoice:
            return obj.id_invoice.invoice_number or obj.id_invoice.id_invoice

        return None

    def get_verified_by_email(self, obj):
        if obj.verified_by:
            return obj.verified_by.email

        return None

    def get_allocated_amount(self, obj):
        return obj.allocated_amount

    def get_available_amount(self, obj):
        return obj.available_amount