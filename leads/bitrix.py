"""Send website inquiries to Bitrix24 CRM as leads (incoming webhook)."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _webhook_base() -> str:
    raw = (getattr(settings, "BITRIX24_WEBHOOK_URL", "") or "").strip()
    if not raw or "your_" in raw.lower() or "xxx" in raw.lower():
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if not host.endswith("bitrix24.ru") and not host.endswith("bitrix24.com"):
        # Still allow custom domains that host Bitrix; require /rest/ path.
        if "/rest/" not in (parsed.path or ""):
            return ""
    if "/rest/" not in (parsed.path or ""):
        return ""
    return raw if raw.endswith("/") else raw + "/"


def is_configured() -> bool:
    return bool(_webhook_base())


def _build_fields(inquiry) -> dict:
    name = (inquiry.name or "").strip() or "Без имени"
    phone = (inquiry.phone or "").strip()
    city = (getattr(inquiry, "city", "") or "").strip()
    message = (inquiry.message or "").strip()
    source = (inquiry.source or "").strip()

    title_bits = ["Заявка с сайта"]
    if name and name != "Без имени":
        title_bits.append(f"— {name}")
    if phone:
        title_bits.append(phone)

    comments = []
    if city:
        comments.append(f"Город: {city}")
    if message:
        comments.append(f"Комментарий: {message}")
    if source:
        comments.append(f"Страница: {source}")
    vehicle = getattr(inquiry, "vehicle", None)
    if vehicle is not None:
        comments.append(f"Авто: {vehicle}")
    comments.append(f"ID заявки на сайте: {inquiry.pk}")

    fields: dict = {
        "TITLE": " ".join(title_bits)[:255],
        "NAME": name[:100],
        "SOURCE_ID": "WEB",
        "SOURCE_DESCRIPTION": "tehnikagoda.ru",
        "OPENED": "Y",
        "COMMENTS": "\n".join(comments),
    }
    if phone:
        fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
    if city:
        fields["ADDRESS_CITY"] = city[:100]

    utm_source = (getattr(inquiry, "utm_source", "") or "").strip()
    utm_medium = (getattr(inquiry, "utm_medium", "") or "").strip()
    utm_campaign = (getattr(inquiry, "utm_campaign", "") or "").strip()
    if utm_source:
        fields["UTM_SOURCE"] = utm_source[:100]
    if utm_medium:
        fields["UTM_MEDIUM"] = utm_medium[:100]
    if utm_campaign:
        fields["UTM_CAMPAIGN"] = utm_campaign[:120]

    return fields


def send_inquiry_to_bitrix(inquiry) -> bool:
    """
    Create a Bitrix24 lead via incoming webhook.

    Returns True on success. Missing config → False (no error).
    """
    base = _webhook_base()
    if not base:
        logger.info("Bitrix24 webhook not configured — skip lead sync")
        return False

    url = f"{base}crm.lead.add.json"
    payload = {"fields": _build_fields(inquiry)}
    try:
        response = requests.post(url, json=payload, timeout=20)
        try:
            data = response.json()
        except Exception:
            data = {}
        lead_id = data.get("result")
        if response.ok and lead_id is not None and "error" not in data:
            logger.info(
                "Bitrix24 lead created (inquiry_id=%s bitrix_id=%s)",
                getattr(inquiry, "pk", None),
                lead_id,
            )
            return True
        logger.error(
            "Bitrix24 lead failed (inquiry_id=%s status=%s body=%s)",
            getattr(inquiry, "pk", None),
            response.status_code,
            (response.text or "")[:400],
        )
        return False
    except Exception:
        logger.exception(
            "Bitrix24 request error (inquiry_id=%s)", getattr(inquiry, "pk", None)
        )
        return False
