EMAIL_STATUS_PENDING = "pending"
EMAIL_STATUS_SENT = "sent"
EMAIL_STATUS_FAILED = "failed"

EMAIL_STATUS_CHOICES = [
    (EMAIL_STATUS_PENDING, "Pending"),
    (EMAIL_STATUS_SENT, "Sent"),
    (EMAIL_STATUS_FAILED, "Failed"),
]

EMAIL_TYPE_TEST = "test"
EMAIL_TYPE_SUBSCRIPTION_EXPIRING = "subscription_expiring"
EMAIL_TYPE_SUBSCRIPTION_EXPIRED = "subscription_expired"
EMAIL_TYPE_PAYMENT_PENDING = "payment_pending"
EMAIL_TYPE_PAYMENT_RECEIVED = "payment_received"
EMAIL_TYPE_DOCUMENT_CREATED = "document_created"

EMAIL_TYPE_CHOICES = [
    (EMAIL_TYPE_TEST, "Test"),
    (EMAIL_TYPE_SUBSCRIPTION_EXPIRING, "Subscription Expiring"),
    (EMAIL_TYPE_SUBSCRIPTION_EXPIRED, "Subscription Expired"),
    (EMAIL_TYPE_PAYMENT_PENDING, "Payment Pending"),
    (EMAIL_TYPE_PAYMENT_RECEIVED, "Payment Received"),
    (EMAIL_TYPE_DOCUMENT_CREATED, "Document Created"),
]