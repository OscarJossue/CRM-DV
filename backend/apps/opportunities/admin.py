from django.contrib import admin

from .models import Lead, OpportunityFollowUp


class OpportunityFollowUpInline(admin.TabularInline):
    model = OpportunityFollowUp
    extra = 0
    fields = (
        "id_user",
        "follow_up_type",
        "note",
        "follow_up_date",
        "next_follow_up_date",
    )
    readonly_fields = (
        "follow_up_date",
    )


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id_lead",
        "opportunity_code",
        "name",
        "id_company",
        "id_client",
        "id_assigned_user",
        "status",
        "approximate_value",
        "id_converted_project",
        "created_at",
    )

    list_filter = (
        "id_company",
        "status",
        "source",
        "created_at",
    )

    search_fields = (
        "opportunity_code",
        "contact_name",
        "first_name",
        "middle_name",
        "last_name",
        "second_last_name",
        "phone",
        "email",
        "address",
        "id_client__name",
        "id_company__name",
    )

    readonly_fields = (
        "opportunity_code",
        "created_at",
        "updated_at",
    )

    inlines = [
        OpportunityFollowUpInline,
    ]


@admin.register(OpportunityFollowUp)
class OpportunityFollowUpAdmin(admin.ModelAdmin):
    list_display = (
        "id_follow_up",
        "id_opportunity",
        "id_user",
        "follow_up_type",
        "follow_up_date",
        "next_follow_up_date",
    )

    search_fields = (
        "id_opportunity__opportunity_code",
        "id_opportunity__contact_name",
        "id_user__email",
        "note",
    )

    list_filter = (
        "follow_up_type",
        "follow_up_date",
    )

    readonly_fields = (
        "follow_up_date",
    )