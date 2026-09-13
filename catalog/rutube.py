"""Normalize Rutube watch/share URLs into safe embed player URLs."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Public watch / embed / private / shorts IDs (hash or legacy numeric).
_RUTUBE_ID_RE = re.compile(
    r"(?:/(?:video(?:/private)?|play/embed|shorts|embed)/)"
    r"(?P<id>[A-Za-z0-9]{6,64})/?",
    re.IGNORECASE,
)


def parse_rutube_embed_url(raw: str | None) -> str:
    """
    Accept a Rutube link (or already-embed URL) and return https://rutube.ru/play/embed/{id}[?p=…].

    Empty input → "". Invalid / non-Rutube → "".
    """
    value = (raw or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = "https://" + value

    try:
        parsed = urlparse(value)
    except ValueError:
        return ""

    host = (parsed.hostname or "").lower()
    if host not in {"rutube.ru", "www.rutube.ru", "m.rutube.ru"}:
        return ""

    match = _RUTUBE_ID_RE.search(parsed.path or "")
    if not match:
        return ""

    video_id = match.group("id")
    query: dict[str, str] = {}
    # Private / link-access videos use ?p=token
    params = parse_qs(parsed.query or "")
    token = (params.get("p") or [None])[0]
    if token:
        query["p"] = token

    path = f"/play/embed/{video_id}"
    return urlunparse(
        ("https", "rutube.ru", path, "", urlencode(query), "")
    )
