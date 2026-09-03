"""Build Content-Security-Policy strings for public / admin responses."""

from __future__ import annotations


def build_public_csp(*, yandex_metrika_id: str = "") -> str:
    script = ["'self'"]
    connect = ["'self'"]
    img = ["'self'", "data:", "blob:"]
    frame = ["'self'"]
    if (yandex_metrika_id or "").strip():
        script += ["https://mc.yandex.ru", "https://mc.yandex.com"]
        connect += [
            "https://mc.yandex.ru",
            "https://mc.yandex.com",
            "wss://mc.yandex.ru",
        ]
        img += ["https://mc.yandex.ru", "https://mc.yandex.com"]
        frame += ["https://mc.yandex.ru", "https://mc.yandex.com"]
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
