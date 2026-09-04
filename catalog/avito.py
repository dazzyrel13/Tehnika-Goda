"""Avito API client: OAuth token + update listing price (site → Avito)."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.avito.ru/token"
UPDATE_PRICE_URL = "https://api.avito.ru/core/v1/items/{item_id}/update_price"
TOKEN_CACHE_KEY = "avito:access_token"
# Avito tokens last ~24h; refresh a bit early.
TOKEN_CACHE_TTL = 20 * 60 * 60

# avito.ru/.../1234567890 or bare digits
_AVITO_ID_RE = re.compile(r"(?:avito\.ru/[^?\s]*?/)?(\d{5,20})(?:\?|$|/|#)", re.I)
_DIGITS_ONLY = re.compile(r"^\d{5,20}$")


class AvitoAPIError(Exception):
    """Raised when Avito API returns an error or is misconfigured."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def is_configured() -> bool:
    client_id = getattr(settings, "AVITO_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "AVITO_CLIENT_SECRET", "") or ""
    return bool(client_id.strip() and client_secret.strip())


def parse_avito_item_id(raw: str | int | None) -> int | None:
    """Accept bare ID or Avito listing URL; return int or None."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = str(raw).strip()
    if not text:
        return None
    if _DIGITS_ONLY.match(text):
        return int(text)
    match = _AVITO_ID_RE.search(text)
    if match:
        return int(match.group(1))
    # Last path segment sometimes is just the id
    digits = re.findall(r"\d{5,20}", text)
    if len(digits) == 1:
        return int(digits[0])
    return None


def clear_token_cache() -> None:
    cache.delete(TOKEN_CACHE_KEY)


def get_access_token(*, force_refresh: bool = False) -> str:
    if not is_configured():
        raise AvitoAPIError("Avito API is not configured (AVITO_CLIENT_ID/SECRET)")

    if not force_refresh:
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return str(cached)

    client_id = settings.AVITO_CLIENT_ID
    client_secret = settings.AVITO_CLIENT_SECRET
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise AvitoAPIError(f"Token request failed: {exc}") from exc

    try:
        payload: dict[str, Any] = response.json()
    except Exception:
        payload = {}

    if not response.ok or "access_token" not in payload:
        detail = payload.get("error_description") or payload.get("error") or response.text[:200]
        raise AvitoAPIError(
            f"Token error HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    token = str(payload["access_token"])
    expires_in = int(payload.get("expires_in") or TOKEN_CACHE_TTL)
    ttl = max(300, min(TOKEN_CACHE_TTL, expires_in - 600))
    cache.set(TOKEN_CACHE_KEY, token, ttl)
    return token


def update_item_price(item_id: int, price_rub: int) -> dict[str, Any]:
    """
    POST /core/v1/items/{item_id}/update_price with {"price": <int rubles>}.
    Retries once on HTTP 401 after refreshing the token.
    """
    if item_id <= 0:
        raise AvitoAPIError("Invalid Avito item_id")
    if price_rub < 0:
        raise AvitoAPIError("Price must be >= 0")

    url = UPDATE_PRICE_URL.format(item_id=int(item_id))
    body = {"price": int(price_rub)}

    def _call(token: str) -> requests.Response:
        return requests.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )

    token = get_access_token()
    try:
        response = _call(token)
    except requests.RequestException as exc:
        raise AvitoAPIError(f"Price update failed: {exc}") from exc

    if response.status_code == 401:
        clear_token_cache()
        token = get_access_token(force_refresh=True)
        try:
            response = _call(token)
        except requests.RequestException as exc:
            raise AvitoAPIError(f"Price update failed: {exc}") from exc

    try:
        payload: dict[str, Any] = response.json() if response.content else {}
    except Exception:
        payload = {}

    if not response.ok:
        err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        detail = (
            (err or {}).get("message")
            or payload.get("message")
            or payload.get("error_description")
            or response.text[:300]
        )
        raise AvitoAPIError(
            f"Price update HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    logger.info("Avito price updated item_id=%s price=%s", item_id, price_rub)
    return payload
