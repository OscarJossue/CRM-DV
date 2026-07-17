from django.contrib import admin

from .models import PlatformPayment


@admin.register(PlatformPayment)
class PlatformPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id_payment",
        "payment_number",
        "id_company",
        "amount",
        "status",
        "method",
        "payment_date",
        "received_by",
    )
    list_filter = ("status", "method", "payment_date")
    search_fields = (
        "payment_number",
        "id_company__name",
        "reference",
        "id_document__document_number",
    )