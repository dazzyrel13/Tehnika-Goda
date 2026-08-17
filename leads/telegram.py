import logging
import re
import time

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


def _build_messages(inquiry) -> tuple[str, str]:
    """Return (html_text, plain_text) for the inquiry notification."""
    safe_name = escape(inquiry.name or "Без имени")
    safe_phone = escape(inquiry.phone or "Без телефона")
    safe_city = escape(getattr(inquiry, "city", "") or "")
    safe_message = escape(inquiry.message or "")
    safe_source = escape(inquiry.source or "")

    html_lines = [
        "🔥 <b>Новая заявка с сайта</b>",
        "",
        f"👤 <b>Имя:</b> {safe_name}",
        f"📞 <b>Телефон:</b> {safe_phone}",
    ]
    if safe_city:
        html_lines.append(f"📍 <b>Город:</b> {safe_city}")
    if safe_message:
        html_lines.append(f"💬 <b>Комментарий:</b> {safe_message}")
    if safe_source:
        html_lines.append(f"🔗 <b>Источник:</b> {safe_source}")

    plain_lines = [
        "Новая заявка с сайта",
        "",
        f"Имя: {inquiry.name or 'Без имени'}",
        f"Телефон: {inquiry.phone or 'Без телефона'}",
    ]
    city = getattr(inquiry, "city", "") or ""
    if city:
        plain_lines.append(f"Город: {city}")
    if inquiry.message:
        plain_lines.append(f"Комментарий: {inquiry.message}")
    if inquiry.source:
        plain_lines.append(f"Источник: {inquiry.source}")

    return "\n".join(html_lines), "\n".join(plain_lines)


def _post_telegram(token: str, chat_id: str, text: str, parse_mode: str | None) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(url, json=payload, timeout=15)
        body = (response.text or "")[:400]
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.ok and data.get("ok") is True:
            return True, body
        return False, body or f"http {response.status_code}"
    except Exception as exc:
        return False, _redact_secrets(str(exc), token)


def send_inquiry_notification(inquiry) -> bool:
    """Send lead notification to Telegram; fail safe on any error."""
    if not _is_configured():
        logger.warning("Telegram not configured: token/chat id is missing")
        return False

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    html_text, plain_text = _build_messages(inquiry)

    # HTML first, then plain fallback; brief retry for transient network blips.
    attempts = (
        (html_text, "HTML"),
        (plain_text, None),
        (plain_text, None),
    )
    last_detail = ""
    for index, (text, parse_mode) in enumerate(attempts):
        if index:
            time.sleep(0.8)
        ok, detail = _post_telegram(token, chat_id, text, parse_mode)
        if ok:
            logger.info(
                "Telegram send ok (inquiry_id=%s parse_mode=%s)",
                getattr(inquiry, "pk", None),
                parse_mode or "plain",
            )
            return True
        last_detail = detail
        logger.error(
            "Telegram send failed (inquiry_id=%s parse_mode=%s): %s",
            getattr(inquiry, "pk", None),
            parse_mode or "plain",
            _redact_secrets(detail, token),
        )

    return False
