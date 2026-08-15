"""Extra security headers and optional admin IP allowlist."""

from __future__ import annotations

import ipaddress

from django.conf import settings
from django.http import HttpResponseForbidden

from utils.client_ip import get_client_ip
from core.admin_url import DEFAULT_ADMIN_URL_PREFIX
from core.csp import build_admin_csp, build_public_csp


class SecurityHeadersMiddleware:
    """Add CSP and related headers not covered by Django SecurityMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        admin_prefix = _admin_prefix()
        if request.path.startswith(admin_prefix) or request.path.rstrip("/") + "/" == admin_prefix:
            csp = getattr(settings, "CONTENT_SECURITY_POLICY_ADMIN", "") or build_admin_csp()
        else:
            csp = build_public_csp(
                yandex_metrika_id=getattr(settings, "YANDEX_METRIKA_ID", "") or ""
            )
        if csp and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = csp
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


class SlidingAuthSessionMiddleware:
    """Keep staff sessions sliding without rewriting anonymous sessions every hit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            request.session.modified = True
        return response


def _admin_prefix() -> str:
    prefix = getattr(settings, "ADMIN_URL_PREFIX", DEFAULT_ADMIN_URL_PREFIX).lstrip("/")
    path = "/" + prefix
    if not path.endswith("/"):
        path += "/"
    return path


def _allowed_networks():
    """
    Parse ADMIN_ALLOWED_IPS.
    None → allowlist disabled (empty setting).
    Empty list → misconfigured entries, fail closed (deny all).
    """
    raw_list = getattr(settings, "ADMIN_ALLOWED_IPS", []) or []
    networks = []
    saw_entry = False
    for raw in raw_list:
        raw = (raw or "").strip()
        if not raw:
            continue
        saw_entry = True
        try:
            networks.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            continue
    if not saw_entry:
        return None
    return networks


class AdminIPAllowlistMiddleware:
    """
    When ADMIN_ALLOWED_IPS is non-empty, only those IPs may access the admin path.
    Empty list = disabled (default for local/dev).
    Unparseable-only list = deny all (do not silently disable).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        networks = _allowed_networks()
        if networks is None:
            return self.get_response(request)
        admin_prefix = _admin_prefix()
        if request.path.startswith(admin_prefix) or request.path.rstrip(
            "/"
        ) + "/" == admin_prefix:
            if not networks:
                return HttpResponseForbidden("Admin access denied for this IP.")
            client = get_client_ip(request)
            if not client or not _ip_allowed(client, networks):
                return HttpResponseForbidden("Admin access denied for this IP.")
        return self.get_response(request)


def _ip_allowed(ip_str: str, networks) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in networks)
