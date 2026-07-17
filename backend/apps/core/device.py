"""Small user-agent helper for the contractor field workspace."""

MOBILE_USER_AGENT_TOKENS = (
    "android",
    "iphone",
    "ipod",
    "mobile",
    "windows phone",
    "opera mini",
    "blackberry",
)


def contractor_ui_mode(request):
    """Return ``mobile`` or ``desktop`` with an optional session override."""
    requested_mode = (request.GET.get("ui") or request.POST.get("contractor_ui") or "").lower()
    if requested_mode in {"mobile", "desktop"}:
        request.session["contractor_ui_mode"] = requested_mode
        return requested_mode

    saved_mode = request.session.get("contractor_ui_mode")
    if saved_mode in {"mobile", "desktop"}:
        return saved_mode

    user_agent = (request.META.get("HTTP_USER_AGENT") or "").lower()
    return "mobile" if any(token in user_agent for token in MOBILE_USER_AGENT_TOKENS) else "desktop"


def request_is_mobile_contractor_ui(request):
    return contractor_ui_mode(request) == "mobile"
