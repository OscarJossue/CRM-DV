from django.contrib import admin

from .models import Estimate, EstimateItem
from .services import generate_estimate_number, recalculate_estimate


class EstimateItemInline(admin.TabularInline):
    model = EstimateItem
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


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "id_estimate",
        "estimate_number",
        "id_company",
        "id_client",
        "id_project",
        "subtotal",
        "tax",
        "discount_amount",
        "total",
        "status",
        "issue_date",
    )

    search_fields = (
        "estimate_number",
        "id_company__name",
        "id_client__name",
        "id_project__name",
        "client_billing_name",
        "project_name",
        "description",
    )

    list_filter = (
        "status",
        "issue_date",
        "id_company",
    )

    readonly_fields = (
        "estimate_number",
        "subtotal",
        "tax",
        "total",
        "issue_date",
        "expiration_date",
        "last_modified_at",
        "sent_at",
        "converted_at",
    )

    inlines = [EstimateItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.estimate_number:
            obj.estimate_number = generate_estimate_number(obj.id_company)

        if not obj.created_by:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        recalculate_estimate(form.instance)