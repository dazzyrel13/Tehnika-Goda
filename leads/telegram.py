import logging
import re

import requests
from django.conf import settings
from django.utils.html import escape

logger = logging.getLogger(__name__)

_BOT_URL_SECRET = re.compile(r"/bot[^/]+/")


def _is_configured() -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    # Guard against placeholder values from local templates.
    if token == "your_bot_token_here" or chat_id == "your_chat_id_here":
        return False
    return True


def _redact_secrets(text: str, token: str = "") -> str:
    """Strip bot token from log lines (requests includes it in HTTPError URLs)."""
    out = str(text or "")
    if token:
        out = out.replace(token, "***")
    return _BOT_URL_SECRET.sub("/bot***/", out)


def send_inquiry_notification(inquiry) -> bool:
    """Send lead notification to Telegram; fail safe on any error."""
    if not _is_configured():
        logger.warning("Telegram not configured: token/chat id is missing")
        return False

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    safe_name = escape(inquiry.name or "Без имени")
    safe_phone = escape(inquiry.phone or "Без телефона")
    safe_city = escape(getattr(inquiry, "city", "") or "")
    safe_message = escape(inquiry.message or "")
    safe_source = escape(inquiry.source or "")

    lines = [
        "🔥 <b>Новая заявка с сайта</b>",
        "",
        f"👤 <b>Имя:</b> {safe_name}",
        f"📞 <b>Телефон:</b> {safe_phone}",
    ]
    if safe_city:
        lines.append(f"📍 <b>Город:</b> {safe_city}")
    if safe_message:
        lines.append(f"💬 <b>Комментарий:</b> {safe_message}")
    if safe_source:
        lines.append(f"🔗 <b>Источник:</b> {safe_source}")

    payload = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", _redact_secrets(str(exc), token))
        return False
