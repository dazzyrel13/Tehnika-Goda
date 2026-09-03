"""Build Content-Security-Policy strings for public / admin responses."""

from __future__ import annotations


def build_public_csp(*, yandex_metrika_id: str = "") -> str:
    script = ["'self'"]
    connect = ["'self'"]
    img = ["'self'", "data:", "blob:"]
    frame = ["'self'"]
    child = ["'self'"]
    if (yandex_metrika_id or "").strip():
        # Hosts from Yandex Metrika CSP docs (RU/.com + static CDN + webvisor).
        ym_hosts = [
            "https://mc.yandex.ru",
            "https://mc.yandex.com",
            "https://mc.webvisor.com",
            "https://mc.webvisor.org",
        ]
        script += ym_hosts + ["https://yastatic.net"]
        connect += ym_hosts + [
            "wss://mc.yandex.ru",
            "wss://mc.yandex.com",
            "wss://mc.webvisor.com",
            "wss://mc.webvisor.org",
        ]
        img += ["https://mc.yandex.ru", "https://mc.yandex.com"]
        # blob: required for Webvisor / clickmap / scroll maps (official docs).
        frame += ["blob:", "https://mc.yandex.ru", "https://mc.yandex.com"]
        child += ["blob:", "https://mc.yandex.ru", "https://mc.yandex.com"]
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        f"script-src {' '.join(script)}; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        f"img-src {' '.join(img)}; "
        f"connect-src {' '.join(connect)}; "
        f"frame-src {' '.join(frame)}; "
        f"child-src {' '.join(child)}; "
    )


def build_admin_csp() -> str:
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self'; "
    )
