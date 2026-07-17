PLATFORM_INTERNAL_COMPANY_NAME = "CEO MARKETING"

PLATFORM_MODULE_DASHBOARD = "platform_dashboard"
PLATFORM_MODULE_COMPANIES = "companies"
PLATFORM_MODULE_PLANS = "platform_plans"
PLATFORM_MODULE_SUBSCRIPTIONS = "platform_subscriptions"
PLATFORM_MODULE_DOCUMENTS = "platform_documents"
PLATFORM_MODULE_PAYMENTS = "platform_payments"
PLATFORM_MODULE_CALENDAR = "platform_calendar"
PLATFORM_MODULE_EMAIL = "platform_email"
PLATFORM_MODULE_NOTIFICATIONS = "platform_notifications"
PLATFORM_MODULE_AUDIT = "platform_audit"
PLATFORM_MODULE_RESOURCES = "dashboard_metrics"
PLATFORM_MODULE_SYSTEM_MONITOR = "system_monitor"

PLATFORM_MODULE_CHOICES = [
    (PLATFORM_MODULE_DASHBOARD, "CRM Admin Dashboard"),
    (PLATFORM_MODULE_COMPANIES, "Companies"),
    (PLATFORM_MODULE_PLANS, "Platform Plans"),
    (PLATFORM_MODULE_SUBSCRIPTIONS, "Subscriptions"),
    (PLATFORM_MODULE_DOCUMENTS, "Platform Documents"),
    (PLATFORM_MODULE_PAYMENTS, "Platform Payments"),
    (PLATFORM_MODULE_CALENDAR, "Platform Calendar"),
    (PLATFORM_MODULE_EMAIL, "Platform Email"),
    (PLATFORM_MODULE_NOTIFICATIONS, "Platform Notifications"),
    (PLATFORM_MODULE_AUDIT, "Platform Audit"),
    (PLATFORM_MODULE_RESOURCES, "Resources Dashboard"),
    (PLATFORM_MODULE_SYSTEM_MONITOR, "System Monitor"),
]

PLATFORM_PERMISSION_ACTIONS = [
    ("can_view", "View"),
    ("can_create", "Create"),
    ("can_edit", "Edit"),
    ("can_delete", "Delete"),
    ("can_approve", "Approve"),
]