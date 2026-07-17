from django.utils.translation import gettext_lazy as _


ACTION_CREATED = "created"
ACTION_UPDATED = "updated"
ACTION_DELETED = "deleted"
ACTION_STATUS_CHANGED = "status_changed"
ACTION_VOIDED = "voided"
ACTION_CANCELLED = "cancelled"
ACTION_APPROVED = "approved"
ACTION_REJECTED = "rejected"
ACTION_SENT = "sent"
ACTION_FILE_UPLOADED = "file_uploaded"
ACTION_PAYMENT_REGISTERED = "payment_registered"
ACTION_PERMISSIONS_UPDATED = "permissions_updated"
ACTION_LOGIN = "login"
ACTION_LOGOUT = "logout"
ACTION_EXPORT = "export"
ACTION_SYSTEM = "system"

ACTION_TYPE_CHOICES = [
    (ACTION_CREATED, _("Created")),
    (ACTION_UPDATED, _("Updated")),
    (ACTION_DELETED, _("Deleted")),
    (ACTION_STATUS_CHANGED, _("Status changed")),
    (ACTION_VOIDED, _("Voided")),
    (ACTION_CANCELLED, _("Cancelled")),
    (ACTION_APPROVED, _("Approved")),
    (ACTION_REJECTED, _("Rejected")),
    (ACTION_SENT, _("Sent")),
    (ACTION_FILE_UPLOADED, _("File uploaded")),
    (ACTION_PAYMENT_REGISTERED, _("Payment registered")),
    (ACTION_PERMISSIONS_UPDATED, _("Permissions updated")),
    (ACTION_LOGIN, _("Signed in")),
    (ACTION_LOGOUT, _("Signed out")),
    (ACTION_EXPORT, _("Exported")),
    (ACTION_SYSTEM, _("System event")),
]

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"
SEVERITY_SECURITY = "security"

SEVERITY_CHOICES = [
    (SEVERITY_INFO, _("Information")),
    (SEVERITY_WARNING, _("Warning")),
    (SEVERITY_CRITICAL, _("Critical")),
    (SEVERITY_SECURITY, _("Security")),
]

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"

RESULT_CHOICES = [
    (RESULT_SUCCESS, _("Successful")),
    (RESULT_FAILURE, _("Failed")),
]

CRITICAL_ACTION_TYPES = {
    ACTION_DELETED,
    ACTION_VOIDED,
    ACTION_CANCELLED,
    ACTION_PERMISSIONS_UPDATED,
}

SECURITY_ACTION_TYPES = {
    ACTION_LOGIN,
    ACTION_LOGOUT,
}
