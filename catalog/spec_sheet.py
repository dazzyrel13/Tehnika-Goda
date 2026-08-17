"""Parse pasted vehicle spec text into key/value rows for a two-column sheet."""

from __future__ import annotations

import re
from html import unescape
from typing import NamedTuple

from django.utils.html import strip_tags

LABEL_RE = re.compile(r"[\[【［]([^\[\]【】［］]{1,80})[\]】］]")
MIN_SPEC_ROWS = 2


class SpecSheet(NamedTuple):
    rows: list[tuple[str, str]]
    rest: str

    @property
    def has_rows(self) -> bool:
        return len(self.rows) >= MIN_SPEC_ROWS


def html_to_text(raw: str) -> str:
    text = raw or ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = strip_tags(text)
    text = unescape(text)
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def parse_spec_sheet(raw: str) -> SpecSheet:
    text = html_to_text(raw)
    if not LABEL_RE.search(text):
        return SpecSheet(rows=[], rest=text.strip())

    parts = LABEL_RE.split(text)
    leftover: list[str] = []
    prefix = (parts[0] or "").strip()
    if prefix:
        leftover.append(prefix)

    rows: list[tuple[str, str]] = []
    index = 1
    while index < len(parts):
        key = " ".join((parts[index] or "").split()).strip(" :：")
        value = parts[index + 1] if index + 1 < len(parts) else ""
        value = re.sub(r"[ \t]*\n[ \t]*", " ", value)
        value = " ".join(value.split()).strip()
        if key:
            rows.append((key, value))
        index += 2

    return SpecSheet(rows=rows, rest="\n\n".join(leftover).strip())
