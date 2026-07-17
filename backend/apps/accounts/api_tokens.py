"""Secure SimpleJWT token endpoints for CRM users."""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code

from .api_auth import ACCESS_DENIED_ERROR
from .security import clear_login_failures, login_is_throttled, register_login_failure


GENERIC_LOGIN_ERROR = "Unable to sign in with the supplied credentials."


class CRMTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue tokens only through the CRM access policy and login limiter."""

    def validate(self, attrs):
        request = self.context.get("request")
        email = (attrs.get(self.username_field) or "").strip().lower()
        attrs[self.username_field] = email

        if login_is_throttled(request, email):
            raise AuthenticationFailed(
                "Too many failed sign-in attempts. Wait and try again.",
                code="login_throttled",
            )

        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            register_login_failure(request, email)
            raise AuthenticationFailed(GENERIC_LOGIN_ERROR, code="invalid_credentials")

        if get_user_runtime_access_code(self.user) != ACCESS_ALLOWED:
            clear_login_failures(request, email)
            raise AuthenticationFailed(ACCESS_DENIED_ERROR, code="account_access_denied")

        clear_login_failures(request, email)
        try:
            from apps.audit.models.choices import ACTION_LOGIN, SEVERITY_SECURITY
            from apps.audit.services import log_system_action

            log_system_action(
                user=self.user,
                module="authentication",
                action="accounts.useraccount:api_login",
                action_type=ACTION_LOGIN,
                request=request,
                object_type="User account",
                object_id=self.user.pk,
                object_label=self.user.email,
                severity=SEVERITY_SECURITY,
            )
        except Exception:
            pass
        return data


class CRMTokenRefreshSerializer(TokenRefreshSerializer):
    """Do not refresh a token for a suspended user or tenant."""

    def validate(self, attrs):
        try:
            refresh = self.token_class(attrs["refresh"])
            user_id = refresh[api_settings.USER_ID_CLAIM]
        except (KeyError, TokenError):
            return super().validate(attrs)

        user_model = get_user_model()
        lookup = {api_settings.USER_ID_FIELD: user_id}
        user = user_model.objects.select_related("id_company").filter(**lookup).first()

        if not user or get_user_runtime_access_code(user) != ACCESS_ALLOWED:
            raise AuthenticationFailed(ACCESS_DENIED_ERROR, code="account_access_denied")

        return super().validate(attrs)


class CRMTokenObtainPairView(TokenObtainPairView):
    serializer_class = CRMTokenObtainPairSerializer


class CRMTokenRefreshView(TokenRefreshView):
    serializer_class = CRMTokenRefreshSerializer
