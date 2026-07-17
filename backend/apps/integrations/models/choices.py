PROVIDER_GOOGLE = "google"

PROVIDER_CHOICES = [
    (PROVIDER_GOOGLE, "Google"),
]

STATUS_CONNECTED = "connected"
STATUS_DISCONNECTED = "disconnected"
STATUS_EXPIRED = "expired"
STATUS_ERROR = "error"
STATUS_REVOKED = "revoked"

CONNECTION_STATUS_CHOICES = [
    (STATUS_CONNECTED, "Connected"),
    (STATUS_DISCONNECTED, "Disconnected"),
    (STATUS_EXPIRED, "Expired"),
    (STATUS_ERROR, "Error"),
    (STATUS_REVOKED, "Revoked"),
]

TOOL_CALENDAR = "calendar"
TOOL_DRIVE = "drive"
TOOL_SHEETS = "sheets"
TOOL_ANALYTICS = "analytics"
TOOL_ADS = "ads"
TOOL_ADS_LEADS = "ads_leads"
TOOL_OAUTH = "oauth"

TOOL_CHOICES = [
    (TOOL_CALENDAR, "Calendar / Meet"),
    (TOOL_DRIVE, "Google Drive"),
    (TOOL_SHEETS, "Google Sheets"),
    (TOOL_ANALYTICS, "Google Analytics"),
    (TOOL_ADS, "Google Ads"),
    (TOOL_ADS_LEADS, "Google Ads / LSA Leads"),
    (TOOL_OAUTH, "Google Connection"),
]

LOG_PENDING = "pending"
LOG_SUCCESS = "success"
LOG_ERROR = "error"
LOG_SKIPPED = "skipped"

LOG_STATUS_CHOICES = [
    (LOG_PENDING, "Pending"),
    (LOG_SUCCESS, "Success"),
    (LOG_ERROR, "Error"),
    (LOG_SKIPPED, "Skipped"),
]

EVENT_DRAFT = "draft"
EVENT_SYNCED = "synced"
EVENT_CANCELLED = "cancelled"
EVENT_ERROR = "error"

EVENT_STATUS_CHOICES = [
    (EVENT_DRAFT, "Draft"),
    (EVENT_SYNCED, "Synced"),
    (EVENT_CANCELLED, "Cancelled"),
    (EVENT_ERROR, "Error"),
]

EXPORT_PENDING = "pending"
EXPORT_COMPLETED = "completed"
EXPORT_ERROR = "error"

EXPORT_STATUS_CHOICES = [
    (EXPORT_PENDING, "Pending"),
    (EXPORT_COMPLETED, "Completed"),
    (EXPORT_ERROR, "Error"),
]

SOURCE_CLIENTS = "clients"
SOURCE_LEADS = "leads"
SOURCE_INVOICES = "invoices"
SOURCE_PAYMENTS = "payments"
SOURCE_SUPPLIERS = "suppliers"
SOURCE_PURCHASES = "supplier_purchases"
SOURCE_ANALYTICS = "analytics"
SOURCE_ADS = "ads"
SOURCE_GOOGLE_LEADS = "google_ads_leads"

SHEET_EXPORT_SOURCE_CHOICES = [
    (SOURCE_CLIENTS, "Clients"),
    (SOURCE_LEADS, "Leads"),
    (SOURCE_INVOICES, "Invoices"),
    (SOURCE_PAYMENTS, "Payments"),
    (SOURCE_SUPPLIERS, "Suppliers"),
    (SOURCE_PURCHASES, "Supplier Purchases"),
    (SOURCE_ANALYTICS, "Analytics Snapshot"),
    (SOURCE_ADS, "Google Ads Snapshot"),
    (SOURCE_GOOGLE_LEADS, "Google Ads / LSA Leads"),
]

GOOGLE_LEAD_SOURCE_WEBHOOK = "google_ads_webhook"
GOOGLE_LEAD_SOURCE_LOCAL_SERVICES = "google_local_services"
GOOGLE_LEAD_SOURCE_LEAD_FORM_API = "google_lead_form_api"

GOOGLE_LEAD_SOURCE_CHOICES = [
    (GOOGLE_LEAD_SOURCE_WEBHOOK, "Google Ads Lead Form Webhook"),
    (GOOGLE_LEAD_SOURCE_LOCAL_SERVICES, "Google Guaranteed / Local Services Ads"),
    (GOOGLE_LEAD_SOURCE_LEAD_FORM_API, "Google Ads Lead Form API"),
]

CRM_LEAD_STATUS_NEW = "new"
CRM_LEAD_STATUS_CONTACTED = "contacted"
CRM_LEAD_STATUS_BOOKED = "booked"
CRM_LEAD_STATUS_LOST = "lost"
CRM_LEAD_STATUS_ARCHIVED = "archived"

GOOGLE_LEAD_CRM_STATUS_CHOICES = [
    (CRM_LEAD_STATUS_NEW, "New"),
    (CRM_LEAD_STATUS_CONTACTED, "Contacted"),
    (CRM_LEAD_STATUS_BOOKED, "Booked"),
    (CRM_LEAD_STATUS_LOST, "Lost"),
    (CRM_LEAD_STATUS_ARCHIVED, "Archived"),
]

REPLY_CHANNEL_CRM_NOTE = "crm_note"
REPLY_CHANNEL_EMAIL = "email"
REPLY_CHANNEL_PHONE = "phone"
REPLY_CHANNEL_WHATSAPP = "whatsapp"
REPLY_CHANNEL_GOOGLE_MESSAGE = "google_message"

REPLY_CHANNEL_CHOICES = [
    (REPLY_CHANNEL_CRM_NOTE, "CRM Note"),
    (REPLY_CHANNEL_EMAIL, "Email"),
    (REPLY_CHANNEL_PHONE, "Phone Call"),
    (REPLY_CHANNEL_WHATSAPP, "WhatsApp"),
    (REPLY_CHANNEL_GOOGLE_MESSAGE, "Google Message"),
]

REPLY_STATUS_DRAFT = "draft"
REPLY_STATUS_LOGGED = "logged"
REPLY_STATUS_SENT = "sent"
REPLY_STATUS_ERROR = "error"

REPLY_STATUS_CHOICES = [
    (REPLY_STATUS_DRAFT, "Draft"),
    (REPLY_STATUS_LOGGED, "Logged in CRM"),
    (REPLY_STATUS_SENT, "Sent"),
    (REPLY_STATUS_ERROR, "Error"),
]
