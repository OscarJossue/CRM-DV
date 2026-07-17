STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"

COMPANY_STATUS_CHOICES = [
    (STATUS_ACTIVE, "Active"),
    (STATUS_INACTIVE, "Inactive"),
]

PLAN_INTERNAL = "internal"
PLAN_STARTER = "starter"
PLAN_PRO = "pro"
PLAN_BUSINESS = "business"

COMPANY_PLAN_CHOICES = [
    (PLAN_INTERNAL, "Internal"),
    (PLAN_STARTER, "Starter"),
    (PLAN_PRO, "Pro"),
    (PLAN_BUSINESS, "Business"),
]


LANGUAGE_ENGLISH = "en"
LANGUAGE_SPANISH = "es"

COMPANY_LANGUAGE_CHOICES = [
    (LANGUAGE_ENGLISH, "English"),
    (LANGUAGE_SPANISH, "Español"),
]
