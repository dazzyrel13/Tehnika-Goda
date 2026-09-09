"""Cookie-based visitor identity — no Django session required for analytics."""

from __future__ import annotations

import re
import secrets

from django.conf import settings

VISITOR_COOKIE_NAME = "tg_vid"
VISITOR_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year
UTM_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign")

_VISITOR_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def new_visitor_id() -> str:
    return secrets.token_hex(16)


def is_valid_visitor_id(value: str | None) -> bool:
    return bool(value and _VISITOR_ID_RE.fullmatch(value))


def read_visitor_id(request) -> str | None:
    raw = (request.COOKIES.get(VISITOR_COOKIE_NAME) or "").strip()
    if is_valid_visitor_id(raw):
        return raw
    # Legacy migration only when a session cookie already exists (avoid creating one).
    session_name = getattr(settings, "SESSION_COOKIE_NAME", "sessionid")
    if session_name in request.COOKIES and getattr(request, "session", None) is not None:
        legacy = (request.session.get("analytics_visitor_id") or "").strip()
        if is_valid_visitor_id(legacy):
            return legacy
    return None


def visitor_id_for_lead(request) -> str:
    """Stable id for Inquiry without forcing a session write."""
    vid = read_visitor_id(request)
    if vid:
        return vid[:64]
    session_name = getattr(settings, "SESSION_COOKIE_NAME", "sessionid")
    if session_name in request.COOKIES and getattr(request, "session", None) is not None:
        return (request.session.session_key or "")[:64]
    return ""


def set_visitor_cookie(response, visitor_id: str) -> None:
    response.set_cookie(
        VISITOR_COOKIE_NAME,
        visitor_id,
        max_age=VISITOR_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        path="/",
    )


def set_utm_cookie(response, key: str, value: str) -> None:
    if key not in UTM_KEYS or not value:
        return
    response.set_cookie(
        key,
        value[:120],
        max_age=UTM_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        path="/",
    )
