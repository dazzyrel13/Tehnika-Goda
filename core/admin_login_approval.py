"""Email approval for staff admin sessions (replaces IP allowlist when enabled)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core import signing
from django.core.cache import cache
from django.dispatch import receiver
from django.urls import reverse

from utils.client_ip import get_client_ip

logger = logging.getLogger(__name__)

APPROVAL_SALT = "admin-login-approval"
APPROVAL_MAX_AGE = 20 * 60
CACHE_APPROVED = "admin_login_approved:"
CACHE_META = "admin_login_meta:"


def approval_enabled() -> bool:
    return bool(getattr(settings, "ADMIN_LOGIN_EMAIL_APPROVAL", False))


def _approved_key(session_key: str) -> str:
    return f"{CACHE_APPROVED}{session_key}"


def _meta_key(session_key: str) -> str:
    return f"{CACHE_META}{session_key}"


def is_session_approved(session_key: str | None) -> bool:
    if not approval_enabled():
        return True
    if not session_key:
        return False
    return cache.get(_approved_key(session_key)) is True


def mark_session_pending(session_key: str, user, request) -> None:
    meta = {
        "username": user.get_username(),
        "ip": get_client_ip(request) or "unknown",
    }
    cache.set(_meta_key(session_key), meta, APPROVAL_MAX_AGE)
    cache.delete(_approved_key(session_key))


def approve_session(session_key: str) -> bool:
    if not cache.get(_meta_key(session_key)):
        return False
    cache.set(_approved_key(session_key), True, APPROVAL_MAX_AGE)
    cache.delete(_meta_key(session_key))
    return True


def clear_session_approval(session_key: str | None) -> None:
    if not session_key:
        return
    cache.delete(_approved_key(session_key))
    cache.delete(_meta_key(session_key))


def make_approval_token(session_key: str, user_id: int) -> str:
    signer = signing.TimestampSigner(salt=APPROVAL_SALT)
    return signer.sign(f"{session_key}:{user_id}")


def parse_approval_token(token: str) -> tuple[str, int] | None:
    signer = signing.TimestampSigner(salt=APPROVAL_SALT)
    try:
        value = signer.unsign(token, max_age=APPROVAL_MAX_AGE)
    except signing.BadSignature:
        return None
    session_key, user_id_str = value.rsplit(":", 1)
    return session_key, int(user_id_str)


def queue_approval_email(*, session_key: str, user, request) -> bool:
    """Queue approval email via Celery so login/2FA is not blocked on SMTP."""
    recipient = (getattr(settings, "ADMIN_LOGIN_APPROVAL_EMAIL", "") or "").strip()
    if not recipient:
        logger.error("ADMIN_LOGIN_APPROVAL_EMAIL is not configured")
        return False

    token = make_approval_token(session_key, user.pk)
    approve_path = reverse("admin_login_approve", kwargs={"token": token})
    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if site_url:
        approve_url = f"{site_url}{approve_path}"
    else:
        approve_url = request.build_absolute_uri(approve_path)

    from core.tasks import send_admin_login_approval_email_task

    send_admin_login_approval_email_task.delay(
        session_key=session_key,
        user_id=user.pk,
        approve_url=approve_url,
        client_ip=get_client_ip(request) or "unknown",
    )
    return True


def _should_gate_user(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


@receiver(user_logged_in)
def request_admin_login_approval(sender, request, user, **kwargs):
    if not approval_enabled() or not _should_gate_user(user):
        return
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    mark_session_pending(session_key, user, request)
    queued = queue_approval_email(session_key=session_key, user=user, request=request)
    request.session["admin_login_email_sent"] = queued


@receiver(user_logged_out)
def clear_admin_login_approval_on_logout(sender, request, user, **kwargs):
    if request is None:
        return
    clear_session_approval(request.session.session_key)
