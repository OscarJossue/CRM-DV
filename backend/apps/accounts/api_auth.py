"""JWT authentication that applies the same access policy as the HTML login."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code


ACCESS_DENIED_ERROR = "This account cannot access the CRM. Contact support."


class CRMJWTAuthentication(JWTAuthentication):
    """Reject access tokens as soon as the user or company loses access."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if get_user_runtime_access_code(user) != ACCESS_ALLOWED:
            raise AuthenticationFailed(ACCESS_DENIED_ERROR, code="account_access_denied")
        return user
