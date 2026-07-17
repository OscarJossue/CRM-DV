from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def integration_encryption_key_check(app_configs, **kwargs):
    """Warn production deployments that rely on the SECRET_KEY fallback."""
    if getattr(settings, "DEBUG", False):
        return []

    configured_key = getattr(settings, "INTEGRATION_ENCRYPTION_KEY", "")
    if configured_key:
        return []

    return [
        Error(
            "INTEGRATION_ENCRYPTION_KEY is not configured.",
            hint=(
                "Set a dedicated Fernet key in the production environment so "
                "Google OAuth secrets and tokens do not share Django SECRET_KEY."
            ),
            id="integrations.E001",
        )
    ]
