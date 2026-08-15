"""Trusted client IP extraction behind a reverse proxy."""

from __future__ import annotations

import ipaddress

from django.conf import settings


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().strip('"').strip("'")
    if not candidate:
        return None
    # Strip optional port from IPv4 host:port (not valid for IPv6 bracket form here)
    if candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def trust_proxy_headers() -> bool:
    """True when the app sits behind a trusted reverse proxy (nginx)."""
    return bool(
        getattr(settings, "BEHIND_HTTPS_PROXY", False)
        or getattr(settings, "TRUST_PROXY_HEADERS", False)
    )


def get_client_ip(request) -> str | None:
    """
    Return the real client IP.

    When TRUST_PROXY_HEADERS / BEHIND_HTTPS_PROXY is enabled, prefer X-Real-IP
    only if the TCP peer looks like our reverse proxy (private Docker IP).
    Loopback peers are direct Gunicorn hits (healthcheck) — ignore spoofed
    headers there, except in automated tests (Django test client is loopback).
    Fall back to the *rightmost* hop of X-Forwarded-For. Never use the
    leftmost XFF value: that is attacker-controlled when clients send XFF.

    Without a trusted proxy, use REMOTE_ADDR only.
    """
    remote = _valid_ip(request.META.get("REMOTE_ADDR"))
    if trust_proxy_headers() and _peer_is_trusted_proxy(remote):
        real_ip = _valid_ip(request.META.get("HTTP_X_REAL_IP"))
        if real_ip:
            return real_ip

        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "") or ""
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            # Rightmost = last proxy hop (nginx $proxy_add_x_forwarded_for).
            for hop in reversed(parts):
                ip = _valid_ip(hop)
                if ip:
                    return ip

    return remote


def _peer_is_trusted_proxy(remote: str | None) -> bool:
    if not remote:
        return False
    try:
        ip = ipaddress.ip_address(remote)
    except ValueError:
        return False
    if ip.is_loopback:
        return bool(getattr(settings, "TESTING", False))
    return bool(ip.is_private)


def get_client_ip_for_ratelimit(request) -> str:
    """django-ratelimit RATELIMIT_IP_META_KEY callable — never returns empty."""
    return get_client_ip(request) or "0.0.0.0"


def get_client_ip_for_axes(request) -> str:
    """django-axes AXES_CLIENT_IP_CALLABLE — never returns empty."""
    return get_client_ip(request) or "0.0.0.0"
