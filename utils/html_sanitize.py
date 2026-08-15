"""HTML allowlist sanitization for rich text stored in the database."""

from __future__ import annotations

from urllib.parse import urlparse

import bleach
from bs4 import BeautifulSoup

# CKEditor 5 + typical article HTML
ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "div",
        "span",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "a",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "img",
        "figure",
        "figcaption",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

# No global class/id — reduces CSS/DOM injection surface from admin HTML.
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}

ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


def _is_local_img_src(src: str) -> bool:
    """Allow only same-origin paths or data/blob URLs (matches public CSP img-src)."""
    raw = (src or "").strip()
    if not raw:
        return False
    if raw.startswith("data:") or raw.startswith("blob:"):
        return True
    if raw.startswith("/") and not raw.startswith("//"):
        return True
    parsed = urlparse(raw)
    # Protocol-relative //evil.com or absolute http(s) — reject for public CSP.
    if parsed.scheme or parsed.netloc:
        return False
    return raw.startswith("/")


def _harden_markup(html: str) -> str:
    """noopener on blank targets; drop external <img> that public CSP would block."""
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a"):
        target = (anchor.get("target") or "").lower()
        if target == "_blank":
            rel_parts = {p for p in (anchor.get("rel") or "").split() if p}
            rel_parts.update({"noopener", "noreferrer"})
            anchor["rel"] = " ".join(sorted(rel_parts))
    for img in soup.find_all("img"):
        if not _is_local_img_src(img.get("src") or ""):
            img.decompose()
    return soup.decode_contents()


def sanitize_html(html: str) -> str:
    if not html:
        return ""
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return _harden_markup(cleaned)
