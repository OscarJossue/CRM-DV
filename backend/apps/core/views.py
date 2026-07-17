from django.shortcuts import render


def permission_denied_view(request, exception=None):
    return render(
        request,
        "403.html",
        {
            "page_title": "403 Forbidden",
            "error_title": "Access Denied",
            "error_message": "You do not have permission to access this section.",
        },
        status=403,
    )