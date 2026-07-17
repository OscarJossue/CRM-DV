from django.conf import settings
from django.db import models
from django.utils import timezone

from ..services.security import decrypt_json, decrypt_text, encrypt_json, encrypt_text, mask_secret

from .choices import (
    CONNECTION_STATUS_CHOICES,
    CRM_LEAD_STATUS_NEW,
    EVENT_STATUS_CHOICES,
    EXPORT_STATUS_CHOICES,
    GOOGLE_LEAD_CRM_STATUS_CHOICES,
    GOOGLE_LEAD_SOURCE_CHOICES,
    GOOGLE_LEAD_SOURCE_WEBHOOK,
    LOG_STATUS_CHOICES,
    PROVIDER_CHOICES,
    PROVIDER_GOOGLE,
    REPLY_CHANNEL_CHOICES,
    REPLY_CHANNEL_CRM_NOTE,
    REPLY_STATUS_CHOICES,
    REPLY_STATUS_LOGGED,
    SHEET_EXPORT_SOURCE_CHOICES,
    STATUS_DISCONNECTED,
    TOOL_CHOICES,
    TOOL_OAUTH,
)


def integration_upload_path(instance, filename):
    company_id = getattr(instance.id_company, "id_company", "company")
    return f"integrations/{company_id}/drive_uploads/{filename}"


class GoogleIntegrationConnection(models.Model):
    id_connection = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="google_integration_connections",
    )
    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES, default=PROVIDER_GOOGLE)
    connected_email = models.EmailField(max_length=180, blank=True, null=True)
    display_name = models.CharField(max_length=160, blank=True, null=True)
    status = models.CharField(max_length=40, choices=CONNECTION_STATUS_CHOICES, default=STATUS_DISCONNECTED, db_index=True)
    scopes = models.JSONField(default=list, blank=True)
    # Encrypted OAuth app credentials and Google tokens.
    oauth_client_id_payload = models.TextField(blank=True, null=True)
    oauth_client_secret_payload = models.TextField(blank=True, null=True)
    token_payload = models.TextField(blank=True, null=True)
    refresh_token_payload = models.TextField(blank=True, null=True)
    access_token_expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    calendar_id = models.CharField(max_length=255, default="primary", blank=True)
    drive_folder_id = models.CharField(max_length=255, blank=True, null=True)
    default_spreadsheet_id = models.CharField(max_length=255, blank=True, null=True)
    analytics_property_id = models.CharField(max_length=80, blank=True, null=True)
    ads_customer_id = models.CharField(max_length=40, blank=True, null=True)
    ads_login_customer_id = models.CharField(max_length=40, blank=True, null=True)
    # Deprecated plaintext column kept for backward compatibility; do not use in templates.
    developer_token = models.CharField(max_length=255, blank=True, null=True)
    developer_token_payload = models.TextField(blank=True, null=True)
    lead_webhook_key_payload = models.TextField(blank=True, null=True)
    auto_create_crm_leads = models.BooleanField(default=True)
    auto_create_crm_leads_from_lsa = models.BooleanField(default=True)
    auto_reply_enabled = models.BooleanField(default=False)
    auto_reply_message = models.TextField(blank=True, null=True)
    last_ads_lead_sync_at = models.DateTimeField(blank=True, null=True)
    last_sync_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_google_connections",
        blank=True,
        null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_google_connections",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_google_connection"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["id_company", "provider"], name="uniq_google_conn_company"),
        ]
        indexes = [
            models.Index(fields=["id_company", "status"], name="int_conn_company_stat_idx"),
            models.Index(fields=["provider"], name="int_conn_provider_idx"),
        ]

    def __str__(self):
        return f"{self.id_company} - {self.get_provider_display()}"

    @property
    def is_connected(self):
        return self.status == "connected"

    @property
    def token_is_expired(self):
        return bool(self.access_token_expires_at and self.access_token_expires_at <= timezone.now())

    @property
    def has_google_app_credentials(self):
        return bool(self.get_oauth_client_id() and self.get_oauth_client_secret())

    @property
    def oauth_client_id_masked(self):
        return mask_secret(self.get_oauth_client_id())

    @property
    def developer_token_masked(self):
        return mask_secret(self.get_developer_token())

    def set_oauth_client_id(self, value):
        self.oauth_client_id_payload = encrypt_text(value or "")

    def get_oauth_client_id(self):
        return decrypt_text(self.oauth_client_id_payload)

    def set_oauth_client_secret(self, value):
        self.oauth_client_secret_payload = encrypt_text(value or "")

    def get_oauth_client_secret(self):
        return decrypt_text(self.oauth_client_secret_payload)

    def set_developer_token(self, value):
        self.developer_token_payload = encrypt_text(value or "")
        self.developer_token = ""

    def get_developer_token(self):
        return decrypt_text(self.developer_token_payload) or (self.developer_token or "")

    def set_lead_webhook_key(self, value):
        self.lead_webhook_key_payload = encrypt_text(value or "")

    def get_lead_webhook_key(self):
        return decrypt_text(self.lead_webhook_key_payload)

    @property
    def lead_webhook_key_masked(self):
        return mask_secret(self.get_lead_webhook_key())

    def set_token_data(self, data):
        self.token_payload = encrypt_json(data or {})

    def get_token_data(self):
        return decrypt_json(self.token_payload)

    def set_refresh_token(self, refresh_token):
        self.refresh_token_payload = encrypt_json({"refresh_token": refresh_token or ""})

    def get_refresh_token(self):
        return decrypt_json(self.refresh_token_payload).get("refresh_token", "")


class IntegrationLog(models.Model):
    id_log = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="integration_logs",
    )
    connection = models.ForeignKey(
        GoogleIntegrationConnection,
        on_delete=models.SET_NULL,
        related_name="logs",
        blank=True,
        null=True,
    )
    tool = models.CharField(max_length=40, choices=TOOL_CHOICES, default=TOOL_OAUTH, db_index=True)
    action = models.CharField(max_length=160)
    status = models.CharField(max_length=30, choices=LOG_STATUS_CHOICES, db_index=True)
    message = models.TextField(blank=True, null=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    external_id = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "integration_log"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["id_company", "tool"], name="int_log_company_tool_idx"),
            models.Index(fields=["status"], name="int_log_status_idx"),
            models.Index(fields=["started_at"], name="int_log_started_idx"),
        ]

    def __str__(self):
        return f"{self.get_tool_display()} - {self.action} - {self.status}"


class GoogleCalendarEventLink(models.Model):
    id_calendar_event = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE)
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.CASCADE, related_name="calendar_events")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, null=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    attendees = models.TextField(blank=True, null=True, help_text="Comma separated emails")
    external_event_id = models.CharField(max_length=255, blank=True, null=True)
    meet_url = models.URLField(max_length=700, blank=True, null=True)
    calendar_html_link = models.URLField(max_length=700, blank=True, null=True)
    status = models.CharField(max_length=30, choices=EVENT_STATUS_CHOICES, default="draft", db_index=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_calendar_event"
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["id_company", "start_at"], name="int_cal_company_start_idx"),
            models.Index(fields=["status"], name="int_cal_status_idx"),
        ]

    def __str__(self):
        return self.title


class GoogleDriveUpload(models.Model):
    id_upload = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE)
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.CASCADE, related_name="drive_uploads")
    title = models.CharField(max_length=220)
    file = models.FileField(upload_to=integration_upload_path, max_length=600)
    source_module = models.CharField(max_length=80, blank=True, null=True)
    external_file_id = models.CharField(max_length=255, blank=True, null=True)
    drive_url = models.URLField(max_length=700, blank=True, null=True)
    status = models.CharField(max_length=30, choices=EXPORT_STATUS_CHOICES, default="pending", db_index=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_drive_upload"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "status"], name="int_drive_company_stat_idx"),
        ]

    def __str__(self):
        return self.title


class GoogleSheetExport(models.Model):
    id_export = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE)
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.CASCADE, related_name="sheet_exports")
    export_source = models.CharField(max_length=60, choices=SHEET_EXPORT_SOURCE_CHOICES)
    spreadsheet_id = models.CharField(max_length=255)
    sheet_name = models.CharField(max_length=120, default="CRM Export")
    rows_exported = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, choices=EXPORT_STATUS_CHOICES, default="pending", db_index=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_sheet_export"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "export_source"], name="int_sheet_company_src_idx"),
        ]

    def __str__(self):
        return f"{self.get_export_source_display()} - {self.created_at:%Y-%m-%d}"


class GoogleAnalyticsSnapshot(models.Model):
    id_snapshot = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE)
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.CASCADE, related_name="analytics_snapshots")
    property_id = models.CharField(max_length=80)
    date_from = models.DateField()
    date_to = models.DateField()
    active_users = models.PositiveIntegerField(default=0)
    sessions = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    raw_response = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_analytics_snapshot"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "property_id"], name="int_ga_company_prop_idx"),
        ]

    def __str__(self):
        return f"GA4 {self.property_id} {self.date_from} - {self.date_to}"


class GoogleAdsSnapshot(models.Model):
    id_snapshot = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE)
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.CASCADE, related_name="ads_snapshots")
    customer_id = models.CharField(max_length=40)
    date_from = models.DateField()
    date_to = models.DateField()
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    clicks = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    conversions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    campaign_rows = models.JSONField(default=list, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_ads_snapshot"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "customer_id"], name="int_ads_company_cust_idx"),
        ]

    def __str__(self):
        return f"Ads {self.customer_id} {self.date_from} - {self.date_to}"


class GoogleAdsLead(models.Model):
    id_ads_lead = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE, related_name="google_ads_leads")
    connection = models.ForeignKey(GoogleIntegrationConnection, on_delete=models.SET_NULL, related_name="ads_leads", blank=True, null=True)
    crm_lead = models.ForeignKey("leads.Lead", on_delete=models.SET_NULL, related_name="google_ads_sources", blank=True, null=True)
    source = models.CharField(max_length=60, choices=GOOGLE_LEAD_SOURCE_CHOICES, default=GOOGLE_LEAD_SOURCE_WEBHOOK, db_index=True)
    external_lead_id = models.CharField(max_length=120, blank=True, null=True)
    external_resource_name = models.CharField(max_length=255, blank=True, null=True)
    customer_id = models.CharField(max_length=40, blank=True, null=True)
    campaign_id = models.CharField(max_length=80, blank=True, null=True)
    adgroup_id = models.CharField(max_length=80, blank=True, null=True)
    form_id = models.CharField(max_length=80, blank=True, null=True)
    gcl_id = models.CharField(max_length=160, blank=True, null=True)
    lead_type = models.CharField(max_length=60, blank=True, null=True)
    lead_status = models.CharField(max_length=60, blank=True, null=True)
    crm_status = models.CharField(max_length=40, choices=GOOGLE_LEAD_CRM_STATUS_CHOICES, default=CRM_LEAD_STATUS_NEW, db_index=True)
    category_id = models.CharField(max_length=160, blank=True, null=True)
    customer_name = models.CharField(max_length=180, blank=True, null=True)
    phone = models.CharField(max_length=60, blank=True, null=True)
    email = models.EmailField(max_length=180, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=40, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    service_interest = models.CharField(max_length=180, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    conversation_text = models.TextField(blank=True, null=True)
    last_reply_message = models.TextField(blank=True, null=True)
    last_reply_at = models.DateTimeField(blank=True, null=True)
    lead_charged = models.BooleanField(default=False)
    lead_feedback_submitted = models.BooleanField(default=False)
    is_test = models.BooleanField(default=False)
    received_at = models.DateTimeField(blank=True, null=True, db_index=True)
    synced_at = models.DateTimeField(blank=True, null=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    raw_conversations = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_google_ads_leads", blank=True, null=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="updated_google_ads_leads", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_google_ads_lead"
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["id_company", "source", "external_lead_id"], name="uniq_google_lead_ext"),
        ]
        indexes = [
            models.Index(fields=["id_company", "source"], name="gads_lead_company_src_idx"),
            models.Index(fields=["id_company", "crm_status"], name="gads_lead_company_stat_idx"),
            models.Index(fields=["external_resource_name"], name="gads_lead_resource_idx"),
        ]

    def __str__(self):
        return self.customer_name or self.external_lead_id or f"Google Lead {self.pk}"

    @property
    def display_contact(self):
        return self.customer_name or self.email or self.phone or "Google Lead"

    @property
    def phone_digits(self):
        return "".join(ch for ch in (self.phone or "") if ch.isdigit())

    @property
    def whatsapp_url(self):
        digits = self.phone_digits
        return f"https://wa.me/{digits}" if digits else ""


class GoogleAdsLeadReply(models.Model):
    id_reply = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE, related_name="google_ads_lead_replies")
    ads_lead = models.ForeignKey(GoogleAdsLead, on_delete=models.CASCADE, related_name="replies")
    channel = models.CharField(max_length=40, choices=REPLY_CHANNEL_CHOICES, default=REPLY_CHANNEL_CRM_NOTE, db_index=True)
    status = models.CharField(max_length=30, choices=REPLY_STATUS_CHOICES, default=REPLY_STATUS_LOGGED, db_index=True)
    subject = models.CharField(max_length=220, blank=True, null=True)
    message = models.TextField()
    external_response_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_google_ads_lead_reply"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["id_company", "channel"], name="gads_reply_company_chan_idx"),
            models.Index(fields=["status"], name="gads_reply_status_idx"),
        ]

    def __str__(self):
        return f"{self.ads_lead} - {self.get_channel_display()}"
