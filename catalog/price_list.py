"""Parse and import the public «авто под заказ» price matrix from Excel."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO

from django.utils.text import slugify
from unidecode import unidecode

logger = logging.getLogger(__name__)

# Multi-word brands first (matched against the start of the model title).
_MULTIWORD_BRANDS = (
    "Mercedes-Benz",
    "Mercedes Benz",
    "Land Rover",
    "Great Wall",
    "Alfa Romeo",
    "GAC Trumpchi",
    "GAC Aion",
)

_BRAND_ALIASES = {
    "audi": "Audi",
    "auidi": "Audi",
    "bmw": "BMW",
    "mercedes-benz": "Mercedes-Benz",
    "mercedes benz": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "toyota": "Toyota",
    "honda": "Honda",
    "hyundai": "Hyundai",
    "nissan": "Nissan",
    "mazda": "Mazda",
    "мазда": "Mazda",
    "kia": "Kia",
    "skoda": "Skoda",
    "škoda": "Skoda",
    "haval": "Haval",
    "chery": "Chery",
    "changan": "Changan",
    "geely": "Geely",
    "byd": "BYD",
    "jetour": "Jetour",
    "jetta": "Jetta",
    "lexus": "Lexus",
    "subaru": "Subaru",
    "mitsubishi": "Mitsubishi",
    "peugeot": "Peugeot",
    "chevrolet": "Chevrolet",
    "wuling": "Wuling",
    "gac": "GAC",
    "gac trumpchi": "GAC",
    "mg": "MG",
    "mg5": "MG",
    "hongqi": "Hongqi",
    "tank": "Tank",
    "zeekr": "Zeekr",
    "li": "Li Auto",
    "li auto": "Li Auto",
    "voyah": "Voyah",
    "deepal": "Deepal",
    "denza": "Denza",
}

_SPACE_RE = re.compile(r"\s+")


@dataclass
class ParsedPriceRow:
    brand: str
    title: str
    price_rub: int


@dataclass
class PriceListImportReport:
    parsed: int = 0
    unique: int = 0
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"parsed={self.parsed} unique={self.unique} "
            f"created={self.created} updated={self.updated} "
            f"deactivated={self.deactivated} errors={len(self.errors)}"
        )


def normalize_title(raw: str) -> str:
    text = _SPACE_RE.sub(" ", (raw or "").strip())
    return text


def extract_brand(title: str) -> str:
    cleaned = normalize_title(title)
    if not cleaned:
        return "Прочее"
    lower = cleaned.lower()
    for multi in _MULTIWORD_BRANDS:
        if lower.startswith(multi.lower()):
            key = multi.lower()
            return _BRAND_ALIASES.get(key, multi)
    # MG5 / MG6 style — brand is MG
    if re.match(r"^mg\d", lower):
        return "MG"
    first = cleaned.split()[0]
    key = first.lower()
    if key in _BRAND_ALIASES:
        return _BRAND_ALIASES[key]
    # Title-case fallback for Latin brands
    if first.isascii():
        return first[:1].upper() + first[1:]
    return first


def _to_price_rub(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        amount = int(round(float(value)))
        return amount if amount > 0 else None
    text = str(value).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    text = re.sub(r"[^\d.]", "", text)
    if not text:
        return None
    try:
        amount = int(Decimal(text).to_integral_value())
    except (InvalidOperation, ValueError):
        return None
    return amount if amount > 0 else None


def _read_sheet_rows(source: str | Path | BinaryIO) -> list[list]:
    """Return raw rows from first sheet (.xlsx via openpyxl, .xls via xlrd)."""
    name = ""
    if isinstance(source, (str, Path)):
        name = str(source).lower()
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")
        if name.endswith(".xls") and not name.endswith(".xlsx"):
            try:
                import xlrd
            except ImportError as exc:
                raise RuntimeError(
                    "Для .xls нужен пакет xlrd. Конвертируйте в .xlsx или "
                    "установите: pip install xlrd"
                ) from exc
            wb = xlrd.open_workbook(str(path))
            sh = wb.sheet_by_index(0)
            return [
                [sh.cell_value(r, c) for c in range(sh.ncols)]
                for r in range(sh.nrows)
            ]
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb[wb.sheetnames[0]]
            return [list(row) for row in ws.iter_rows(values_only=True)]
        finally:
            wb.close()

    # file-like: try openpyxl first, then xlrd
    from openpyxl import load_workbook

    try:
        wb = load_workbook(source, read_only=True, data_only=True)
        try:
            ws = wb[wb.sheetnames[0]]
            return [list(row) for row in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    except Exception:
        if hasattr(source, "seek"):
            source.seek(0)
        try:
            import xlrd
        except ImportError as exc:
            raise RuntimeError("Не удалось прочитать Excel (нужен .xlsx или xlrd)") from exc
        data = source.read() if hasattr(source, "read") else source
        wb = xlrd.open_workbook(file_contents=data)
        sh = wb.sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]


def _find_columns(header: list) -> tuple[int, int]:
    labels = [str(c or "").strip().lower() for c in header]
    title_idx = None
    price_idx = None
    for i, label in enumerate(labels):
        if title_idx is None and label in {"название", "name", "модель", "title"}:
            title_idx = i
        if price_idx is None and label in {"цена", "price", "price_rub", "стоимость"}:
            price_idx = i
    if title_idx is None or price_idx is None:
        # Fallback: col B = title, col F = price (Telegram/Bot export layout)
        title_idx = 1 if len(header) > 1 else 0
        price_idx = 5 if len(header) > 5 else min(2, len(header) - 1)
    return title_idx, price_idx


def parse_price_list(source: str | Path | BinaryIO) -> list[ParsedPriceRow]:
    """Parse Excel and collapse duplicates to min price per title."""
    rows = _read_sheet_rows(source)
    if not rows:
        return []
    title_idx, price_idx = _find_columns(rows[0])
    best: dict[str, ParsedPriceRow] = {}
    for raw in rows[1:]:
        if not raw or title_idx >= len(raw):
            continue
        title = normalize_title(str(raw[title_idx] or ""))
        if not title:
            continue
        price = _to_price_rub(raw[price_idx] if price_idx < len(raw) else None)
        if price is None:
            continue
        brand = extract_brand(title)
        key = title.casefold()
        existing = best.get(key)
        if existing is None or price < existing.price_rub:
            best[key] = ParsedPriceRow(brand=brand, title=title, price_rub=price)
    # Stable sort: brand then title
    return sorted(best.values(), key=lambda r: (r.brand.casefold(), r.title.casefold()))


def brand_sort_key(brand: str) -> tuple:
    """Popular demand brands first, then A–Z."""
    priority = {
        "BMW": 0,
        "Audi": 1,
        "Mercedes-Benz": 2,
        "Volkswagen": 3,
        "Toyota": 4,
        "Honda": 5,
        "Hyundai": 6,
        "Kia": 7,
        "Lexus": 8,
        "Haval": 9,
        "Chery": 10,
        "Changan": 11,
        "Geely": 12,
        "BYD": 13,
        "Jetour": 14,
        "Jetta": 15,
    }
    return (priority.get(brand, 100), brand.casefold())


def resolve_brand_slug(brand: str) -> str:
    """Match catalog Brand.slug when possible."""
    from catalog.models import Brand

    wanted = slugify(unidecode(brand))
    if not wanted:
        return ""
    exact = Brand.objects.filter(slug=wanted).values_list("slug", flat=True).first()
    if exact:
        return exact
    # Try aliases / name contains
    by_name = (
        Brand.objects.filter(name__iexact=brand)
        .values_list("slug", flat=True)
        .first()
    )
    if by_name:
        return by_name
    # Common slug aliases
    aliases = {
        "mercedes-benz": "mercedes-benz",
        "skoda": "skoda",
        "volkswagen": "volkswagen",
    }
    alt = aliases.get(wanted)
    if alt:
        found = Brand.objects.filter(slug=alt).values_list("slug", flat=True).first()
        if found:
            return found
    return ""


def import_price_list(
    source: str | Path | BinaryIO,
    *,
    replace: bool = False,
    dry_run: bool = False,
) -> PriceListImportReport:
    from catalog.models import PriceListItem

    report = PriceListImportReport()
    try:
        parsed = parse_price_list(source)
    except Exception as exc:
        report.errors.append(str(exc))
        return report

    report.parsed = len(parsed)
    # re-dedup already done; unique == len
    report.unique = len(parsed)
    if dry_run:
        return report

    seen_titles: set[str] = set()
    brand_slug_cache: dict[str, str] = {}

    for index, row in enumerate(parsed):
        seen_titles.add(row.title)
        if row.brand not in brand_slug_cache:
            brand_slug_cache[row.brand] = resolve_brand_slug(row.brand)
        defaults = {
            "brand": row.brand,
            "brand_slug": brand_slug_cache[row.brand],
            "price_rub": row.price_rub,
            "sort_order": index * 10,
            "is_active": True,
        }
        obj, created = PriceListItem.objects.update_or_create(
            title=row.title,
            defaults=defaults,
        )
        if created:
            report.created += 1
        else:
            report.updated += 1

    if replace:
        qs = PriceListItem.objects.exclude(title__in=seen_titles)
        report.deactivated = qs.update(is_active=False)

    return report


def grouped_price_list(*, active_only: bool = True):
    """Return [(brand, brand_anchor, catalog_url|None, [items...]), ...] sorted."""
    from catalog.models import PriceListItem

    qs = PriceListItem.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    qs = qs.order_by("sort_order", "brand", "title")

    groups: dict[str, list] = {}
    meta: dict[str, tuple[str, str | None]] = {}
    for item in qs:
        groups.setdefault(item.brand, []).append(item)
        if item.brand not in meta:
            meta[item.brand] = (item.brand_anchor, item.catalog_brand_url())

    ordered = sorted(groups.keys(), key=brand_sort_key)
    result = []
    for brand in ordered:
        anchor, url = meta[brand]
        result.append(
            {
                "brand": brand,
                "anchor": anchor,
                "catalog_url": url,
                "items": groups[brand],
                "heading": f"{brand} из Китая — цены",
            }
        )
    return result
