"""SEO helpers: SITE_URL parsing, absolute links, Sites framework sync."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

# Query params that must not appear in canonical URLs.
_STRIP_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "yclid",
        "gclid",
        "fbclid",
        "ysclid",
        "_openstat",
    }
)


def site_base_url() -> str:
    return (settings.SITE_URL or "http://127.0.0.1:8000").rstrip("/")


def site_protocol() -> str:
    return urlparse(site_base_url()).scheme or "https"


def site_domain() -> str:
    return urlparse(site_base_url()).netloc or "127.0.0.1:8000"


def absolute_url(path: str) -> str:
    """Join SITE_URL with a path or return absolute URLs unchanged."""
    if not path:
        return site_base_url() + "/"
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return site_base_url() + path


def trim_meta_description(text: str, limit: int = 160) -> str:
    """Shorten meta description for search snippets."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def canonical_url_for_request(request) -> str:
    """Build a canonical URL from the request, stripping tracking params."""
    parsed = urlparse(request.get_full_path())
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in _STRIP_QUERY_KEYS and not k.lower().startswith("utm_")
    ]
    clean = urlunparse(
        ("", "", parsed.path, "", urlencode(query_pairs, doseq=True), "")
    )
    return absolute_url(clean)


def sync_site_from_settings() -> None:
    """Keep django.contrib.sites in sync with SITE_URL (used by sitemaps)."""
    try:
        from django.contrib.sites.models import Site
    except Exception:
        return

    domain = site_domain()
    name = "Техника Года"
    try:
        site = Site.objects.filter(pk=settings.SITE_ID).first()
        if site is None:
            Site.objects.create(pk=settings.SITE_ID, domain=domain, name=name)
            return
        if site.domain != domain or site.name != name:
            site.domain = domain
            site.name = name
            site.save(update_fields=["domain", "name"])
    except (OperationalError, ProgrammingError):
        # Migrations / empty DB during startup.
        pass
