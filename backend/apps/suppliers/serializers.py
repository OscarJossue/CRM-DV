from rest_framework import serializers

from .models import Supplier, SupplierDocument, SupplierOffer, SupplierPurchase, SupplierPurchaseItem
from .forms import validate_supplier_document_file


class SupplierSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_supplier", read_only=True)
    company_name_display = serializers.CharField(source="company_name", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "id_supplier",
            "id_company",
            "supplier_code",
            "company_name",
            "company_name_display",
            "contact_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "website",
            "tax_id",
            "supplier_type",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "id_supplier", "supplier_code", "created_at", "updated_at"]


class SupplierOfferSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_supplier_offer", read_only=True)
    supplier_name = serializers.CharField(source="id_supplier.company_name", read_only=True)

    class Meta:
        model = SupplierOffer
        fields = [
            "id",
            "id_supplier_offer",
            "id_company",
            "id_supplier",
            "supplier_name",
            "offer_type",
            "name",
            "product_code",
            "category",
            "description",
            "unit",
            "estimated_price",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "id_supplier_offer", "supplier_name", "created_at", "updated_at"]



    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        supplier = attrs.get("id_supplier") or getattr(self.instance, "id_supplier", None)
        if user and user.is_authenticated and not user.is_superuser and supplier and supplier.id_company_id != user.id_company_id:
            raise serializers.ValidationError("The selected supplier does not belong to your company.")
        return attrs

class SupplierPurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPurchaseItem
        fields = [
            "id_supplier_purchase_item",
            "id_purchase",
            "id_offer",
            "item_name",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "tax_amount",
            "total",
        ]
        read_only_fields = ["id_supplier_purchase_item", "total"]


class SupplierPurchaseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_supplier_purchase", read_only=True)
    supplier_name = serializers.CharField(source="id_supplier.company_name", read_only=True)
    items = SupplierPurchaseItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierPurchase
        fields = [
            "id",
            "id_supplier_purchase",
            "id_company",
            "id_supplier",
            "supplier_name",
            "purchase_number",
            "external_document_number",
            "purchase_date",
            "category",
            "description",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total",
            "paid_amount",
            "balance_due",
            "status",
            "payment_status",
            "notes",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "id_supplier_purchase",
            "supplier_name",
            "purchase_number",
            "subtotal",
            "tax_amount",
            "total",
            "balance_due",
            "payment_status",
            "created_at",
            "updated_at",
        ]



    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        supplier = attrs.get("id_supplier") or getattr(self.instance, "id_supplier", None)
        if user and user.is_authenticated and not user.is_superuser and supplier and supplier.id_company_id != user.id_company_id:
            raise serializers.ValidationError("The selected supplier does not belong to your company.")
        return attrs

class SupplierDocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_supplier_document", read_only=True)

    class Meta:
        model = SupplierDocument
        fields = [
            "id",
            "id_supplier_document",
            "id_company",
            "id_supplier",
            "id_purchase",
            "title",
            "document_type",
            "file",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "id_supplier_document", "created_at"]

    def validate_file(self, value):
        return validate_supplier_document_file(value)

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        supplier = attrs.get("id_supplier") or getattr(self.instance, "id_supplier", None)
        purchase = attrs.get("id_purchase") or getattr(self.instance, "id_purchase", None)
        if purchase and supplier and purchase.id_supplier_id != supplier.id_supplier:
            raise serializers.ValidationError("The selected purchase does not belong to the selected supplier.")
        if user and user.is_authenticated and not user.is_superuser:
            if supplier and supplier.id_company_id != user.id_company_id:
                raise serializers.ValidationError("The selected supplier does not belong to your company.")
            if purchase and purchase.id_company_id != user.id_company_id:
                raise serializers.ValidationError("The selected purchase does not belong to your company.")
        return attrs
