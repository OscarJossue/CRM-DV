from django.contrib import admin

from .models import (
    GoogleAdsLead,
    GoogleAdsLeadReply,
    GoogleAdsSnapshot,
    GoogleAnalyticsSnapshot,
    GoogleCalendarEventLink,
    GoogleDriveUpload,
    GoogleIntegrationConnection,
    GoogleSheetExport,
    IntegrationLog,
)


@admin.register(GoogleIntegrationConnection)
class GoogleIntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ("id_connection", "id_company", "provider", "connected_email", "status", "has_google_app_credentials", "last_sync_at", "updated_at")
    list_filter = ("provider", "status", "updated_at")
    search_fields = ("id_company__name", "connected_email")
    readonly_fields = (
        "created_at",
        "updated_at",
        "oauth_client_id_payload",
        "oauth_client_secret_payload",
        "token_payload",
        "refresh_token_payload",
        "developer_token_payload",
    )
    exclude = ("developer_token",)


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ("id_log", "id_company", "tool", "action", "status", "started_at", "finished_at")
    list_filter = ("tool", "status", "started_at")
    search_fields = ("id_company__name", "action", "message", "external_id")


admin.site.register(GoogleCalendarEventLink)
admin.site.register(GoogleDriveUpload)
admin.site.register(GoogleSheetExport)
admin.site.register(GoogleAnalyticsSnapshot)
admin.site.register(GoogleAdsSnapshot)


@admin.register(GoogleAdsLead)
class GoogleAdsLeadAdmin(admin.ModelAdmin):
    list_display = ("id_ads_lead", "id_company", "source", "customer_name", "phone", "email", "crm_status", "received_at", "crm_lead")
    list_filter = ("source", "crm_status", "is_test", "received_at")
    search_fields = ("customer_name", "phone", "email", "external_lead_id", "external_resource_name")
    readonly_fields = ("raw_payload", "raw_conversations", "created_at", "updated_at")


@admin.register(GoogleAdsLeadReply)
class GoogleAdsLeadReplyAdmin(admin.ModelAdmin):
    list_display = ("id_reply", "id_company", "ads_lead", "channel", "status", "created_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("ads_lead__customer_name", "message", "subject")
