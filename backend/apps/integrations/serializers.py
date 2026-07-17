from rest_framework import serializers

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


class GoogleIntegrationConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleIntegrationConnection
        exclude = ("oauth_client_id_payload", "oauth_client_secret_payload", "token_payload", "refresh_token_payload", "developer_token", "developer_token_payload", "lead_webhook_key_payload")
        read_only_fields = ("id_company", "created_by", "updated_by", "created_at", "updated_at")


class IntegrationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationLog
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "started_at", "finished_at")


class GoogleCalendarEventLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleCalendarEventLink
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "external_event_id", "meet_url", "calendar_html_link", "status", "error_message")


class GoogleDriveUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleDriveUpload
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "external_file_id", "drive_url", "status", "error_message")


class GoogleSheetExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleSheetExport
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "rows_exported", "status", "error_message")


class GoogleAnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAnalyticsSnapshot
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "raw_response", "created_at")


class GoogleAdsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsSnapshot
        fields = "__all__"
        read_only_fields = ("id_company", "created_by", "campaign_rows", "raw_response", "created_at")


class GoogleAdsLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsLead
        fields = "__all__"
        read_only_fields = ("id_company", "connection", "crm_lead", "created_by", "updated_by", "raw_payload", "raw_conversations", "created_at", "updated_at")


class GoogleAdsLeadReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsLeadReply
        fields = "__all__"
        read_only_fields = ("id_company", "ads_lead", "created_by", "created_at")
