import os
from datetime import timedelta
from pathlib import Path
from celery.schedules import crontab

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Local commands read the project-root .env. Docker Compose injects the same
# variables directly into containers, so this remains harmless in Docker.
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name, default="False"):
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes", "on")


DEBUG = env_bool("DEBUG", "True")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key" if DEBUG else "").strip()
INTEGRATION_ENCRYPTION_KEY = os.getenv("INTEGRATION_ENCRYPTION_KEY", "").strip()
CREDENTIAL_ENCRYPTION_KEY = os.getenv(
    "CREDENTIAL_ENCRYPTION_KEY",
    (INTEGRATION_ENCRYPTION_KEY or SECRET_KEY) if DEBUG else "",
).strip()
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", SECRET_KEY if DEBUG else "").strip()

_unsafe_secret_markers = ("change", "generate", "replace", "example", "dev-secret")


def secret_is_unsafe(value, *, minimum_length=32):
    normalized = (value or "").strip().lower()
    return (
        len(normalized) < minimum_length
        or any(marker in normalized for marker in _unsafe_secret_markers)
    )


if not DEBUG and secret_is_unsafe(SECRET_KEY):
    raise ImproperlyConfigured(
        "Set a unique production SECRET_KEY with at least 32 random characters; placeholder values are rejected."
    )

if not DEBUG and secret_is_unsafe(INTEGRATION_ENCRYPTION_KEY):
    raise ImproperlyConfigured(
        "Set a separate production INTEGRATION_ENCRYPTION_KEY with at least 32 random characters."
    )

if not DEBUG and (
    secret_is_unsafe(CREDENTIAL_ENCRYPTION_KEY)
    or CREDENTIAL_ENCRYPTION_KEY in {SECRET_KEY, INTEGRATION_ENCRYPTION_KEY}
):
    raise ImproperlyConfigured(
        "Set a separate production CREDENTIAL_ENCRYPTION_KEY with at least 32 random characters."
    )

if not DEBUG and (secret_is_unsafe(JWT_SIGNING_KEY) or JWT_SIGNING_KEY == SECRET_KEY):
    raise ImproperlyConfigured(
        "Set a separate production JWT_SIGNING_KEY with at least 32 random characters."
    )

_allowed_hosts_default = "localhost,127.0.0.1,0.0.0.0,backend" if DEBUG else ""
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", _allowed_hosts_default).split(",")
    if host.strip()
]

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS cannot be empty in production.")

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000" if DEBUG else "",
    ).split(",")
    if origin.strip()
]
CRM_PUBLIC_BASE_URL = os.getenv("CRM_PUBLIC_BASE_URL", "").rstrip("/") #url para pdf contract

DJANGO_APPS = [
    "django_prometheus",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.companies.apps.CompaniesConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.company_modules.apps.CompanyModulesConfig",
    "apps.employees.apps.EmployeesConfig",
    "apps.clients.apps.ClientsConfig",
    "apps.opportunities.apps.OpportunitiesConfig",
    "apps.leads.apps.LeadsConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.inspections.apps.InspectionsConfig",
    "apps.contractor_portal.apps.ContractorPortalConfig",
    "apps.user_activities.apps.UserActivitiesConfig",
    "apps.estimates.apps.EstimatesConfig",
    "apps.invoices.apps.InvoicesConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.suppliers.apps.SuppliersConfig",
    "apps.integrations.apps.IntegrationsConfig",
    "apps.languages.apps.LanguagesConfig",
    "apps.smtp_settings.apps.SmtpSettingsConfig",
    "apps.contracts.apps.ContractsConfig",
    "apps.evidence.apps.EvidenceConfig",
    "apps.supervision.apps.SupervisionConfig",
    "apps.calendar_events.apps.CalendarEventsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.dashboard_metrics",
    "apps.system_monitor",

    # Platform apps
    "apps.platform_users.apps.PlatformUsersConfig",
    "apps.platform_audit.apps.PlatformAuditConfig",
    "apps.platform_notifications.apps.PlatformNotificationsConfig",
    "apps.platform_calendar.apps.PlatformCalendarConfig",
    "apps.platform_payments.apps.PlatformPaymentsConfig",
    "apps.platform_documents.apps.PlatformDocumentsConfig",
    "apps.platform_core.apps.PlatformCoreConfig",
    "apps.platform_plans.apps.PlatformPlansConfig",
    "apps.platform_subscriptions.apps.PlatformSubscriptionsConfig",
    "apps.platform_email.apps.PlatformEmailConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.CompanyLanguageMiddleware",
    "apps.platform_core.middleware.PlatformSubscriptionAccessMiddleware",
    "apps.audit.middleware.AuditRequestContextMiddleware",
    "apps.core.middleware.ModuleAccessControlMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.crm_context",
                "apps.platform_users.context_processors.platform_users_context",
                "apps.notifications.context_processors.notification_bell_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "crm_saas"),
        "USER": os.getenv("POSTGRES_USER", "crm_user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "crm_password"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

CACHE_URL = os.getenv("CACHE_URL", "").strip()
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
            "TIMEOUT": 300,
            "KEY_PREFIX": "ceo_crm",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ceo-crm-local",
        }
    }

LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "8"))
LOGIN_MAX_FAILURES_PER_IP = int(os.getenv("LOGIN_MAX_FAILURES_PER_IP", "40"))
LOGIN_FAILURE_WINDOW_SECONDS = int(os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "900"))

AUTH_USER_MODEL = "accounts.UserAccount"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": int(os.getenv("PASSWORD_MIN_LENGTH", "10"))},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.api_auth.CRMJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.ReactAdminPagination",
    "PAGE_SIZE": 10,
}

SIMPLE_JWT = {
    "USER_ID_FIELD": "id_user",
    "USER_ID_CLAIM": "user_id",
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=int(os.getenv("JWT_ACCESS_HOURS", "8"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

CORS_EXPOSE_HEADERS = [
    "Content-Range",
    "X-Total-Count",
]

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "nexxtjob_language"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

#TOMCAT
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  

STATICFILES_DIRS = [
    BASE_DIR / "static",
]
#---

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Unified CRM history retention. Routine events remain queryable for 3 days;
# destructive and security-sensitive events remain for 7 days.
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "3"))
AUDIT_CRITICAL_RETENTION_DAYS = int(os.getenv("AUDIT_CRITICAL_RETENTION_DAYS", "7"))

CELERY_BEAT_SCHEDULE = {
    "purge-expired-crm-history": {
        "task": "audit.purge_expired_system_logs",
        "schedule": crontab(hour=3, minute=20),
    },
}


# Platform Email / SMTP configuration

# Platform Email / SMTP configuration
# This SMTP is only for CEO MARKETING SaaS administration emails.
# Do not mix this with company operational SMTP settings.

PLATFORM_EMAIL_BACKEND = os.getenv(
    "PLATFORM_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

PLATFORM_EMAIL_HOST = os.getenv("PLATFORM_EMAIL_HOST", "")
PLATFORM_EMAIL_PORT = int(os.getenv("PLATFORM_EMAIL_PORT", "587"))
PLATFORM_EMAIL_HOST_USER = os.getenv("PLATFORM_EMAIL_HOST_USER", "")
PLATFORM_EMAIL_HOST_PASSWORD = os.getenv("PLATFORM_EMAIL_HOST_PASSWORD", "")
PLATFORM_EMAIL_USE_TLS = env_bool("PLATFORM_EMAIL_USE_TLS", "True")
PLATFORM_EMAIL_USE_SSL = env_bool("PLATFORM_EMAIL_USE_SSL", "False")

PLATFORM_DEFAULT_FROM_EMAIL = os.getenv(
    "PLATFORM_DEFAULT_FROM_EMAIL",
    "CEO Marketing CRM <noreply@ceomarketingusa.com>",
)

# General Django email configuration.
# Used by Django auth flows such as password reset.
# If EMAIL_* values are not defined, it falls back to PLATFORM_EMAIL_*.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    PLATFORM_EMAIL_BACKEND,
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    PLATFORM_EMAIL_HOST,
)

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        str(PLATFORM_EMAIL_PORT),
    )
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    PLATFORM_EMAIL_HOST_USER,
)

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    PLATFORM_EMAIL_HOST_PASSWORD,
)

EMAIL_USE_TLS = env_bool(
    "EMAIL_USE_TLS",
    str(PLATFORM_EMAIL_USE_TLS),
)

EMAIL_USE_SSL = env_bool(
    "EMAIL_USE_SSL",
    str(PLATFORM_EMAIL_USE_SSL),
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    PLATFORM_DEFAULT_FROM_EMAIL,
)

SERVER_EMAIL = os.getenv(
    "SERVER_EMAIL",
    DEFAULT_FROM_EMAIL,
)

EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))


LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Session, proxy and transport security. Production defaults are intentionally
# strict; local development remains available with DEBUG=True.
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", "False")
USE_X_FORWARDED_HOST = TRUST_PROXY_HEADERS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_HEADERS else None
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", "False" if DEBUG else "True")
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", "False" if DEBUG else "True")
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", "False" if DEBUG else "True")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 12)))
SESSION_SAVE_EVERY_REQUEST = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", "False" if DEBUG else "True")
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", "False")

