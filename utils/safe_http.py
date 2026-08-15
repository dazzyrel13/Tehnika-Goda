"""Outbound HTTP helpers with redirect-safe SSRF checks and DNS pinning."""

from __future__ import annotations

import ipaddress
import socket
import threading
from contextlib import contextmanager
from urllib.parse import urljoin, urlparse

import requests

REDIRECT_STATUS = {301, 302, 303, 307, 308}
DEFAULT_TIMEOUT = 20

# Real resolver — never replace this reference after install.
_REAL_GETADDRINFO = socket.getaddrinfo
_TLS = threading.local()


def _normalize_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address):
    """Unwrap IPv4-mapped IPv6 (::ffff:127.0.0.1) before SSRF checks."""
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped if mapped is not None else ip


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    ip = _normalize_ip(ip)
    return not ip.is_global


def _gai_with_optional_pin(host, port, family=0, type=0, proto=0, flags=0):
    """
    Thread-local DNS pin for SSRF-safe fetches.

    Installed once on ``socket.getaddrinfo`` so concurrent requests cannot
    clobber each other's process-global monkeypatch.
    """
    pin_map = getattr(_TLS, "pin_map", None)
    if pin_map:
        pinned = pin_map.get(host)
        if pinned is not None:
            ip_str = str(pinned)
            port_num = int(port) if port is not None and str(port).isdigit() else port
            if pinned.version == 6:
                return [
                    (
                        socket.AF_INET6,
                        socket.SOCK_STREAM,
                        proto or 0,
                        "",
                        (ip_str, int(port_num or 0), 0, 0),
                    )
                ]
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    proto or 0,
                    "",
                    (ip_str, int(port_num or 0)),
                )
            ]
    return _REAL_GETADDRINFO(host, port, family, type, proto, flags)


if not getattr(socket.getaddrinfo, "_turbodv_dns_pin", False):
    _gai_with_optional_pin._turbodv_dns_pin = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _gai_with_optional_pin


@contextmanager
def _dns_pin(hostname: str, pinned_ip: ipaddress.IPv4Address | ipaddress.IPv6Address):
    pin_map = getattr(_TLS, "pin_map", None)
    if pin_map is None:
        pin_map = {}
        _TLS.pin_map = pin_map
    ip_str = str(pinned_ip)
    previous = {
        hostname: pin_map.get(hostname),
        ip_str: pin_map.get(ip_str),
    }
    pin_map[hostname] = pinned_ip
    pin_map[ip_str] = pinned_ip
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                pin_map.pop(key, None)
            else:
                pin_map[key] = old


def _iter_host_ips(hostname: str):
    # Always use the real resolver for policy checks (ignore any active pin).
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            for res in _REAL_GETADDRINFO(hostname, None, family, socket.SOCK_STREAM):
                yield ipaddress.ip_address(res[4][0])
        except OSError:
            continue


def is_safe_request_url(url: str) -> bool:
    """
    Return True if URL scheme/host are acceptable and all resolved IPs are public.
    Rejects credentials in URL, non-http(s) schemes, and missing hostnames.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname
        if not host:
            return False
        # Integer/hex IPv4 literals (http://2130706433/) bypass some resolvers.
        if host.isdigit() or host.lower().startswith("0x"):
            return False

        seen = False
        for ip in _iter_host_ips(host):
            seen = True
            if _is_disallowed_ip(ip):
                return False
        return seen
    except Exception:
        return False


def _pick_public_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    ips = list(_iter_host_ips(hostname))
    if not ips:
        raise ValueError(f"Cannot resolve host: {hostname}")
    for ip in ips:
        if _is_disallowed_ip(ip):
            raise ValueError(f"Unsafe IP for host {hostname}: {ip}")
    return ips[0]


def fetch_url_bytes(
    url: str,
    *,
    max_bytes: int,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict | None = None,
    max_redirects: int = 5,
) -> tuple[bytes, str]:
    """
    GET url without automatic redirects; re-validates each redirect target.
    Pins DNS to a previously validated public IP for the TCP connect (mitigates rebinding).
    Reads up to max_bytes of response body (streaming).
    Returns (body_bytes, final_url).
    """
    hdrs = headers or {}
    current = url
    session = requests.Session()
    for _ in range(max_redirects + 1):
        if not is_safe_request_url(current):
            raise ValueError(f"Unsafe URL rejected: {current}")

        parsed = urlparse(current)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Unsafe URL rejected: {current}")

        pinned_ip = _pick_public_ip(hostname)
        with _dns_pin(hostname, pinned_ip):
            with session.get(
                current,
                allow_redirects=False,
                timeout=timeout,
                headers=hdrs,
                stream=True,
            ) as resp:
                if resp.status_code in REDIRECT_STATUS:
                    loc = resp.headers.get("Location")
                    if not loc:
                        raise ValueError("Redirect without Location header")
                    current = urljoin(current, loc)
                    continue

                resp.raise_for_status()
                total = 0
                chunks: list[bytes] = []
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"Response exceeds {max_bytes} bytes")
                    chunks.append(chunk)
                return b"".join(chunks), current

    raise ValueError("Too many redirects")


def fetch_url_text(
    url: str,
    *,
    max_bytes: int,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict | None = None,
) -> str:
    data, _final = fetch_url_bytes(
        url, max_bytes=max_bytes, timeout=timeout, headers=headers
    )
    return data.decode("utf-8", errors="replace")
