"""Import vehicles from Avito autoload Excel (.xlsx)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable

from urllib.parse import urljoin

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from utils.safe_http import is_safe_request_url

from .avito import parse_avito_item_id
from .engine_type import detect_engine_type
from .listing_ingest import (
    MAX_GALLERY_UPLOADS,
    attach_vehicle_images,
    create_vehicle_draft,
    get_or_create_brand,
    get_or_create_category,
)
from .models import Vehicle
from .spec_sheet import LABEL_RE, html_to_text

logger = logging.getLogger(__name__)

SHEET_NAME = "Автомобили-С пробегом"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\d+")

SPEC_KEYS = (
    ("GenerationId", "generation"),
    ("ModificationId", "modification"),
    ("ComplectationId", "complectation"),
    ("VIN", "vin"),
    ("Owners", "owners"),
    ("PTS", "pts"),
    ("DriveType", "drive"),
    ("EngineSize", "engine_size"),
    ("Doors", "doors"),
    ("WheelType", "wheel"),
    ("Accident", "accident"),
    ("FuelType", "fuel"),
)


@dataclass
class AvitoListing:
    row_number: int
    avito_id: int | None
    make: str
    model: str
    title: str
    short_title: str
    year: int
    mileage: int
    color: str
    price_rub: Decimal | None
    description: str
    body_type: str
    transmission: str
    fuel_type: str
    horsepower: int | None
    image_urls: list[str] = field(default_factory=list)
    specs: dict = field(default_factory=dict)


@dataclass
class ImportReport:
    created: int = 0
    skipped: int = 0
    linked: int = 0
    photos_filled: int = 0
    descriptions_updated: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_ids: list[int] = field(default_factory=list)
    linked_ids: list[int] = field(default_factory=list)
    skipped_reasons: list[str] = field(default_factory=list)
    linked_reasons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Создано: {self.created}, привязан Avito ID: {self.linked}, "
            f"фото догружено: {self.photos_filled}, "
            f"описание обновлено: {self.descriptions_updated}, "
            f"пропущено: {self.skipped}, "
            f"ошибок: {len(self.errors)}, предупреждений: {len(self.warnings)}."
        )


def normalize_text(value: str | None) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u202f", " ")
    text = text.casefold()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def _cell_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_int(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = "".join(_DIGITS_RE.findall(str(value).replace("\u00a0", " ")))
    if not digits:
        return default
    try:
        return int(digits)
    except ValueError:
        return default


def _parse_price(value) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(int(value)))
        except (InvalidOperation, ValueError, OverflowError):
            return None
    digits = "".join(_DIGITS_RE.findall(str(value).replace("\u00a0", " ")))
    if not digits:
        return None
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def _split_image_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\s*\|\s*", str(raw).strip())
    urls: list[str] = []
    for part in parts:
        url = part.strip()
        if not url:
            continue
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        urls.append(url)
    return urls[:MAX_GALLERY_UPLOADS]


def _find_header_row(rows: list[tuple]) -> tuple[int, list[str]]:
    for idx, row in enumerate(rows[:12]):
        cells = [_cell_str(c) for c in row]
        if "Id" in cells and "AvitoId" in cells and "Make" in cells:
            return idx, cells
    raise ValueError(
        f"Не найдены заголовки Id/AvitoId/Make на листе «{SHEET_NAME}»."
    )


def parse_avito_xlsx(source: str | Path | BinaryIO) -> list[AvitoListing]:
    """Parse Avito autoload workbook into listing rows."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Нужен пакет openpyxl. Установите: pip install openpyxl"
        ) from exc

    wb = load_workbook(source, read_only=True, data_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(
                f"В файле нет листа «{SHEET_NAME}». Есть: {', '.join(wb.sheetnames)}"
            )
        ws = wb[SHEET_NAME]
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if not rows:
        return []

    header_idx, headers = _find_header_row(rows)
    col = {name: i for i, name in enumerate(headers) if name}

    def get(row, key: str):
        idx = col.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    listings: list[AvitoListing] = []
    for row_offset, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        make = _cell_str(get(row, "Make"))
        if not make:
            continue
        # Skip Avito instruction / validation helper rows.
        if make in {"Обязательный", "Подробнее о параметре", "Марка"}:
            continue
        model = _cell_str(get(row, "Model"))
        year = _parse_int(get(row, "Year"))
        if year < 1980:
            continue

        avito_raw = get(row, "AvitoId") or get(row, "Id")
        avito_id = parse_avito_item_id(avito_raw)
        title = _cell_str(get(row, "Title"))
        short_title = f"{make} {model}".strip()
        if not title:
            title = short_title

        specs: dict[str, str] = {}
        for excel_key, spec_key in SPEC_KEYS:
            val = _cell_str(get(row, excel_key))
            if val:
                specs[spec_key] = val
        color = _cell_str(get(row, "Color"))
        if color:
            specs["color"] = color

        listings.append(
            AvitoListing(
                row_number=row_offset,
                avito_id=avito_id,
                make=make,
                model=model,
                title=title,
                short_title=short_title,
                year=year,
                mileage=_parse_int(get(row, "Kilometrage")),
                color=color,
                price_rub=_parse_price(get(row, "Price")),
                description=_cell_str(get(row, "Description")),
                body_type=_cell_str(get(row, "BodyType")),
                transmission=_cell_str(get(row, "Transmission")),
                fuel_type=_cell_str(get(row, "FuelType")),
                horsepower=_parse_int(get(row, "Power")) or None,
                image_urls=_split_image_urls(_cell_str(get(row, "ImageUrls"))),
                specs=specs,
            )
        )
    return listings


def titles_match(listing: AvitoListing, vehicle: Vehicle) -> bool:
    site_title = normalize_text(vehicle.title)
    brand_name = normalize_text(getattr(vehicle.brand, "name", "") or "")
    site_brand_model = normalize_text(
        f"{brand_name} {normalize_text(vehicle.model)}".strip()
    )
    avito_title = normalize_text(listing.title)
    avito_short = normalize_text(listing.short_title)
    if not site_title:
        return False
    if site_title == avito_title:
        return True
    if site_brand_model and site_brand_model == avito_short:
        return True
    if site_title == avito_short:
        return True
    return False


def fingerprint_match(listing: AvitoListing, vehicle: Vehicle) -> bool:
    if int(vehicle.year or 0) != int(listing.year or 0):
        return False
    if int(vehicle.mileage or 0) != int(listing.mileage or 0):
        return False
    if normalize_text(vehicle.color) != normalize_text(listing.color):
        return False
    return titles_match(listing, vehicle)


def find_existing_vehicle(
    listing: AvitoListing,
    *,
    by_avito_id: dict[int, Vehicle],
    candidates: Iterable[Vehicle],
) -> Vehicle | None:
    if listing.avito_id and listing.avito_id in by_avito_id:
        return by_avito_id[listing.avito_id]
    for vehicle in candidates:
        if fingerprint_match(listing, vehicle):
            return vehicle
    return None


def _format_mileage(mileage: int) -> str:
    return f"{int(mileage):,}".replace(",", " ")


SPEC_LABELS = {
    "generation": "Поколение",
    "modification": "Модификация",
    "complectation": "Комплектация",
    "vin": "VIN",
    "owners": "Владельцев по ПТС",
    "pts": "ПТС",
    "drive": "Привод",
    "engine_size": "Объём двигателя",
    "doors": "Дверей",
    "wheel": "Руль",
    "accident": "Состояние",
}


def build_spec_description(listing: AvitoListing) -> str:
    """
    Build site table-friendly text: [Field] value rows + marketing text.
    """
    lines: list[str] = []

    def add(label: str, value) -> None:
        text = _cell_str(value)
        if text:
            lines.append(f"[{label}] {text}")

    add("Название автомобиля", listing.short_title or listing.title)
    add("Марка", listing.make)
    add("Модель", listing.model)
    if listing.year:
        add("Год выпуска", listing.year)
    if listing.mileage:
        add("Пробег", f"{_format_mileage(listing.mileage)} километров")
    add("Цвет", listing.color)
    add("Коробка передач", listing.transmission)
    add("Тип кузова", listing.body_type)
    add("Тип двигателя", listing.fuel_type)
    if listing.horsepower:
        add("Мощность двигателя", f"{listing.horsepower} л.с.")
    for key, label in SPEC_LABELS.items():
        add(label, listing.specs.get(key))

    rest = html_to_text(listing.description or "").strip()
    # Drop rest if it already looks like a full bracket sheet (avoid nesting).
    if rest and LABEL_RE.search(rest) and rest.count("[") >= 3:
        return rest
    if rest:
        lines.append("")
        lines.append(rest)
    return "\n".join(lines).strip()


def description_needs_reformat(raw: str | None) -> bool:
    text = raw or ""
    if not text.strip():
        return True
    sheet_ok = bool(LABEL_RE.search(text)) and text.count("[") + text.count("【") >= 2
    if sheet_ok:
        return False
    # Raw Avito HTML / plain marketing without bracket rows.
    return True


def vehicle_needs_photos(vehicle: Vehicle) -> bool:
    if vehicle.main_image:
        return False
    return not vehicle.gallery.exists()


def _fetch_image_bytes(url: str) -> bytes:
    """
    Download image following redirects without DNS pinning.

    Avito feed URLs redirect to *.img.avito.st; DNS-pinned fetch breaks TLS there.
    Each hop is still validated with is_safe_request_url (public IPs only).
    """
    current = url
    session = requests.Session()
    for _ in range(6):
        if not is_safe_request_url(current):
            raise ValueError(f"Unsafe URL rejected: {current}")
        with session.get(
            current,
            allow_redirects=False,
            timeout=45,
            headers=IMAGE_HEADERS,
            stream=True,
        ) as resp:
            if resp.status_code in {301, 302, 303, 307, 308}:
                loc = resp.headers.get("Location")
                if not loc:
                    raise ValueError("Redirect without Location")
                current = urljoin(current, loc)
                continue
            resp.raise_for_status()
            total = 0
            chunks: list[bytes] = []
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ValueError(f"Response exceeds {MAX_IMAGE_BYTES} bytes")
                chunks.append(chunk)
            return b"".join(chunks)
    raise ValueError("Too many redirects")


def _download_images(urls: list[str]) -> tuple[list[SimpleUploadedFile], list[str]]:
    uploads: list[SimpleUploadedFile] = []
    warnings: list[str] = []
    for index, url in enumerate(urls, start=1):
        if not is_safe_request_url(url):
            warnings.append(f"Небезопасный URL фото пропущен: {url[:80]}")
            continue
        try:
            raw = _fetch_image_bytes(url)
            img = Image.open(BytesIO(raw))
            img.verify()
            img = Image.open(BytesIO(raw))
            fmt = (img.format or "JPEG").upper()
            ext_map = {"JPEG": ".jpg", "JPG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
            ext = ext_map.get(fmt, ".jpg")
            uploads.append(
                SimpleUploadedFile(
                    f"avito_{index}{ext}",
                    raw,
                    content_type=f"image/{ext.lstrip('.')}",
                )
            )
        except Exception as exc:
            warnings.append(f"Фото не скачалось ({url[:60]}…): {exc}")
            logger.info("Avito image download failed url=%s err=%s", url[:120], exc)
    return uploads, warnings


def _attach_listing_photos(
    vehicle: Vehicle, listing: AvitoListing
) -> tuple[int, list[str]]:
    if not listing.image_urls:
        return 0, []
    uploads, warnings = _download_images(listing.image_urls)
    if not uploads:
        return 0, warnings
    added, skipped = attach_vehicle_images(vehicle, uploads)
    if skipped:
        warnings.append(f"пропущено файлов фото: {skipped}")
    return added, warnings


def enrich_existing_vehicle(
    vehicle: Vehicle,
    listing: AvitoListing,
    *,
    download_photos: bool,
    update_description: bool = True,
) -> tuple[list[str], dict[str, bool]]:
    """Fill missing Avito photos / reformat description on an existing row."""
    warnings: list[str] = []
    changed = {"photos": False, "description": False}

    if update_description and description_needs_reformat(vehicle.description):
        vehicle.description = build_spec_description(listing)
        vehicle.save(update_fields=["description"], skip_image_queue=True)
        changed["description"] = True

    if download_photos and vehicle_needs_photos(vehicle):
        added, photo_warnings = _attach_listing_photos(vehicle, listing)
        warnings.extend(photo_warnings)
        if added:
            changed["photos"] = True

    return warnings, changed


def create_from_listing(
    listing: AvitoListing,
    *,
    download_photos: bool = True,
) -> tuple[Vehicle, list[str]]:
    brand, _ = get_or_create_brand(listing.make)
    category, _ = get_or_create_category(
        "Автомобили",
        body_type=listing.body_type,
        haystack=listing.description,
        mileage=listing.mileage,
    )
    vehicle = create_vehicle_draft(
        title=listing.short_title[:160] or listing.title[:160],
        brand=brand,
        category=category,
        model=listing.model,
        year=listing.year,
        mileage=listing.mileage,
        horsepower=listing.horsepower,
        transmission=listing.transmission,
        body_type=listing.body_type,
        color=listing.color,
        engine_type=detect_engine_type(listing.fuel_type),
        price_rub=listing.price_rub,
        description=build_spec_description(listing),
        specs=listing.specs,
        is_new=False,
    )
    warnings: list[str] = []
    if listing.avito_id:
        vehicle.avito_item_id = listing.avito_id
        vehicle.save(update_fields=["avito_item_id"], skip_image_queue=True)

    if download_photos and listing.image_urls:
        added, photo_warnings = _attach_listing_photos(vehicle, listing)
        warnings.extend(photo_warnings)
        if not added and listing.image_urls:
            warnings.append("фото не прикрепились.")
    return vehicle, warnings


def import_avito_listings(
    listings: list[AvitoListing],
    *,
    dry_run: bool = False,
    download_photos: bool = True,
) -> ImportReport:
    report = ImportReport()
    vehicles = list(
        Vehicle.objects.select_related("brand").only(
            "id",
            "title",
            "model",
            "year",
            "mileage",
            "color",
            "avito_item_id",
            "description",
            "main_image",
            "brand__name",
        )
    )
    by_avito_id = {
        int(v.avito_item_id): v for v in vehicles if v.avito_item_id
    }

    for listing in listings:
        try:
            existing = find_existing_vehicle(
                listing, by_avito_id=by_avito_id, candidates=vehicles
            )
            if existing is not None:
                linked_now = False
                if (
                    listing.avito_id
                    and not existing.avito_item_id
                    and listing.avito_id not in by_avito_id
                ):
                    reason = (
                        f"Строка {listing.row_number}: к «{existing.title}» "
                        f"(id={existing.pk}) привязан AvitoId {listing.avito_id}"
                    )
                    if dry_run:
                        report.linked += 1
                        report.linked_ids.append(existing.pk)
                        report.linked_reasons.append(reason + " (проверка)")
                        linked_now = True
                    else:
                        existing.avito_item_id = listing.avito_id
                        existing.save(
                            update_fields=["avito_item_id"], skip_image_queue=True
                        )
                        by_avito_id[int(listing.avito_id)] = existing
                        report.linked += 1
                        report.linked_ids.append(existing.pk)
                        report.linked_reasons.append(reason)
                        linked_now = True

                if dry_run:
                    if description_needs_reformat(existing.description):
                        report.descriptions_updated += 1
                    if download_photos and vehicle_needs_photos(existing):
                        report.photos_filled += 1
                    if not linked_now:
                        report.skipped += 1
                        report.skipped_reasons.append(
                            f"Строка {listing.row_number}: уже есть "
                            f"«{existing.title}» (id={existing.pk}) — проверка"
                        )
                    continue

                warnings, changed = enrich_existing_vehicle(
                    existing,
                    listing,
                    download_photos=download_photos,
                )
                report.warnings.extend(
                    f"Строка {listing.row_number}: {w}" for w in warnings
                )
                if changed["photos"]:
                    report.photos_filled += 1
                if changed["description"]:
                    report.descriptions_updated += 1

                if not linked_now:
                    report.skipped += 1
                    reason = (
                        f"Строка {listing.row_number}: уже есть "
                        f"«{existing.title}» (id={existing.pk})"
                    )
                    if listing.avito_id and existing.avito_item_id == listing.avito_id:
                        reason += " — совпал AvitoId"
                    elif existing.avito_item_id and listing.avito_id:
                        if existing.avito_item_id != listing.avito_id:
                            reason += (
                                f" — совпали название/год/пробег/цвет, "
                                f"на сайте уже другой AvitoId {existing.avito_item_id}"
                            )
                        else:
                            reason += " — совпали название/год/пробег/цвет"
                    else:
                        reason += " — совпали название/год/пробег/цвет"
                    extras = []
                    if changed["photos"]:
                        extras.append("фото догружены")
                    if changed["description"]:
                        extras.append("описание в шаблон")
                    if extras:
                        reason += " (" + ", ".join(extras) + ")"
                    report.skipped_reasons.append(reason)
                continue

            if dry_run:
                report.created += 1
                report.created_ids.append(0)
                continue

            vehicle, warnings = create_from_listing(
                listing, download_photos=download_photos
            )
            report.created += 1
            report.created_ids.append(vehicle.pk)
            report.warnings.extend(
                f"Строка {listing.row_number}: {w}" if not w.startswith("Строка") else w
                for w in warnings
            )
            vehicles.append(vehicle)
            if vehicle.avito_item_id:
                by_avito_id[int(vehicle.avito_item_id)] = vehicle
        except Exception as exc:
            logger.exception("Avito row import failed row=%s", listing.row_number)
            report.errors.append(f"Строка {listing.row_number}: {exc}")

    return report


def import_avito_xlsx(
    source: str | Path | BinaryIO,
    *,
    dry_run: bool = False,
    download_photos: bool = True,
) -> ImportReport:
    listings = parse_avito_xlsx(source)
    return import_avito_listings(
        listings, dry_run=dry_run, download_photos=download_photos
    )
