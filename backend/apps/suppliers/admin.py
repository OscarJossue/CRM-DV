from django.contrib import admin

from .models import Supplier, SupplierDocument, SupplierOffer, SupplierPurchase, SupplierPurchaseItem


class SupplierOfferInline(admin.TabularInline):
    model = SupplierOffer
    extra = 0
    fields = ("name", "product_code", "category", "unit", "estimated_price", "status")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("supplier_code", "company_name", "id_company", "supplier_type", "phone", "email", "status")
    list_filter = ("status", "supplier_type", "id_company")
    search_fields = ("supplier_code", "company_name", "contact_name", "email", "phone", "tax_id")
    inlines = [SupplierOfferInline]


@admin.register(SupplierOffer)
class SupplierOfferAdmin(admin.ModelAdmin):
    list_display = ("name", "product_code", "id_supplier", "category", "estimated_price", "status")
    list_filter = ("category", "status")
    search_fields = ("name", "product_code", "description", "id_supplier__company_name")


class SupplierPurchaseItemInline(admin.TabularInline):
    model = SupplierPurchaseItem
    extra = 0
    fields = ("item_name", "quantity", "unit", "unit_price", "tax_amount", "total")
    readonly_fields = ("total",)


@admin.register(SupplierPurchase)
class SupplierPurchaseAdmin(admin.ModelAdmin):
    list_display = ("purchase_number", "id_supplier", "purchase_date", "total", "paid_amount", "balance_due", "status", "payment_status")
    list_filter = ("status", "payment_status", "category", "id_company")
    search_fields = ("purchase_number", "external_document_number", "id_supplier__company_name", "description")
    inlines = [SupplierPurchaseItemInline]


@admin.register(SupplierDocument)
class SupplierDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "id_supplier", "id_purchase", "created_at")
    list_filter = ("document_type", "id_company")
    search_fields = ("title", "id_supplier__company_name", "id_purchase__purchase_number")
