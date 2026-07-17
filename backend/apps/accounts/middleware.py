from django.contrib.auth import logout
from django.shortcuts import redirect

from apps.core.access_policy import ACCESS_ALLOWED, get_user_runtime_access_code


class ActiveUserRequiredMiddleware:
    """Force logout when the current runtime access policy denies the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            path = request.path or ""
            allowed_path = (
                path.startswith("/login/")
                or path.startswith("/logout/")
                or path.startswith("/accounts/logout/")
                or path.startswith("/admin/")
                or path.startswith("/static/")
                or path.startswith("/media/")
                or path.startswith("/account-suspended/")
            )

            if not allowed_path and get_user_runtime_access_code(user) != ACCESS_ALLOWED:
                logout(request)
                return redirect("accounts:login")

        return self.get_response(request)
