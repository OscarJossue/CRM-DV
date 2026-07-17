from django.contrib import admin

from .models import PlatformDocument, PlatformDocumentItem


class PlatformDocumentItemInline(admin.TabularInline):
    model = PlatformDocumentItem
    extra = 0


@admin.register(PlatformDocument)
class PlatformDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id_document",
        "document_number",
        "id_company",
        "document_type",
        "status",
        "issue_date",
        "due_date",
        "total",
    )
    list_filter = ("document_type", "status", "issue_date", "due_date")
    search_fields = ("document_number", "id_company__name")
    inlines = [PlatformDocumentItemInline]


@admin.register(PlatformDocumentItem)
class PlatformDocumentItemAdmin(admin.ModelAdmin):
    list_display = ("id_document_item", "id_document", "description", "quantity", "unit_price", "subtotal")
    search_fields = ("description", "id_document__document_number")