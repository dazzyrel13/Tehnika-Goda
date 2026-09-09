"""Fetch CNY rate from the Bank of Russia daily XML feed."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from utils.safe_http import fetch_url_text

logger = logging.getLogger(__name__)

CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CBR_TIMEOUT = 10


class CbrRateError(Exception):
    """CBR fetch or parse failed."""


def fetch_cbr_cny_rate() -> Decimal:
    """
    Return rubles per 1 CNY from CBR XML_daily.asp.

    Handles Nominal (e.g. rate for N units → divide by Nominal).
    """
    try:
        text = fetch_url_text(
            CBR_DAILY_URL,
            timeout=CBR_TIMEOUT,
            max_bytes=2 * 1024 * 1024,
        )
    except Exception as exc:
        logger.warning("CBR fetch failed: %s", exc)
        raise CbrRateError(f"Не удалось скачать курс ЦБ: {exc}") from exc

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise CbrRateError("Ответ ЦБ не является корректным XML") from exc

    for valute in root.findall("Valute"):
        char_code = (valute.findtext("CharCode") or "").strip().upper()
        if char_code != "CNY":
            continue
        raw_value = (valute.findtext("Value") or "").strip().replace(",", ".")
        raw_nominal = (valute.findtext("Nominal") or "1").strip().replace(",", ".")
        try:
            value = Decimal(raw_value)
            nominal = Decimal(raw_nominal)
        except InvalidOperation as exc:
            raise CbrRateError("ЦБ вернул нечисловой курс CNY") from exc
        if nominal <= 0:
            raise CbrRateError("ЦБ вернул нулевой Nominal для CNY")
        rate = (value / nominal).quantize(Decimal("0.0001"))
        if rate <= 0:
            raise CbrRateError("ЦБ вернул неположительный курс CNY")
        return rate

    raise CbrRateError("В ответе ЦБ нет валюты CNY")
