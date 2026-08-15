"""Validation helpers for lead / inquiry spam filtering."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|"
    r"\b(?:bit\.ly|goo\.gl|t\.co|tinyurl\.com|vk\.cc)/\S+|"
    r"\b(?:[a-z0-9\-]+\.)+[a-z]{2,}(?:/[^\s]*)?)",
    re.I,
)
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

RU_PHONE_ERROR = (
    "Укажите российский номер: +7 или 8, затем 10 цифр "
    "(например +7 924 149-00-13)."
)
CYRILLIC_NAME_ERROR = "Укажите имя кириллицей (как в паспорте или как к вам обращаться)."
CYRILLIC_CITY_ERROR = "Укажите город кириллицей."
SPAM_TEXT_ERROR = "Проверьте текст — ссылки и email в заявке не принимаются."


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_ru_phone(value: str) -> str:
    """
    Accept RU numbers starting with +7 / 7 / 8 (11 digits) or 10 local digits.
    Return canonical form +7XXXXXXXXXX.
    """
    digits = digits_only(value)
    if len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]

    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError(RU_PHONE_ERROR, code="ru_phone")

    # Reject obvious non-RU patterns padded into +7 (e.g. pasted US numbers).
    # Valid: 7 + 10 digits. Mobile often 79…; landline area codes also OK.
    if digits[1] == "0":
        raise ValidationError(RU_PHONE_ERROR, code="ru_phone")

    return f"+{digits}"


def assert_no_spam_markers(value: str, *, allow_empty: bool = False) -> str:
    text = (value or "").strip()
    if not text:
        if allow_empty:
            return ""
        raise ValidationError("Заполните поле.", code="required")
    if EMAIL_RE.search(text) or URL_RE.search(text):
        raise ValidationError(SPAM_TEXT_ERROR, code="spam_text")
    return text


def assert_cyrillic_label(value: str, error_message: str) -> str:
    text = assert_no_spam_markers(value)
    if not CYRILLIC_RE.search(text):
        raise ValidationError(error_message, code="cyrillic_required")
    # Mostly-Latin names with a token Cyrillic char are still spammy.
    latin = len(LATIN_LETTER_RE.findall(text))
    cyr = len(CYRILLIC_RE.findall(text))
    if latin and latin > cyr:
        raise ValidationError(error_message, code="cyrillic_required")
    if sum(ch.isdigit() for ch in text) > 3:
        raise ValidationError(error_message, code="suspicious_name")
    return text
