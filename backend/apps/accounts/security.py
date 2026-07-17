"""Authentication security helpers.

No password, token or raw email is written to the cache key. The limiter is a
small defense-in-depth layer; Django password hashing and CSRF/session security
remain the primary controls.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache


def _normalize_email(email):
    return (email or "").strip().lower()


def _client_ip(request):
    if not request:
        return "unknown"

    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip() or "unknown"

    return request.META.get("REMOTE_ADDR", "unknown") or "unknown"


def _digest(value):
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _principal_key(request, email):
    return "crm-login:principal:" + _digest(f"{_client_ip(request)}|{_normalize_email(email)}")


def _ip_key(request):
    return "crm-login:ip:" + _digest(_client_ip(request))


def _get_count(key):
    try:
        return int(cache.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def login_is_throttled(request, email):
    principal_limit = int(getattr(settings, "LOGIN_MAX_FAILURES", 8))
    ip_limit = int(getattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 40))
    return (
        _get_count(_principal_key(request, email)) >= principal_limit
        or _get_count(_ip_key(request)) >= ip_limit
    )


def _increment(key, timeout):
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def register_login_failure(request, email):
    timeout = int(getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", 900))
    _increment(_principal_key(request, email), timeout)
    _increment(_ip_key(request), timeout)


def clear_login_failures(request, email):
    cache.delete(_principal_key(request, email))
