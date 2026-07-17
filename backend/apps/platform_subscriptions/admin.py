from django.contrib import admin

from .models import PlatformSubscription


@admin.register(PlatformSubscription)
class PlatformSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id_subscription",
        "id_company",
        "id_plan",
        "status",
        "start_date",
        "renewal_date",
        "end_date",
    )
    list_filter = ("status", "renewal_date")
    search_fields = ("id_company__name", "id_plan__name")