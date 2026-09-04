"""Fill a vehicle draft from pasted spec text and optional photos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.core.files.uploadedfile import UploadedFile
from django.db.models import Max
from django.utils.text import slugify
from PIL import Image
from unidecode import unidecode

from .models import Brand, Category, Vehicle, VehicleImage
from .engine_type import detect_engine_type
from .spec_sheet import parse_spec_sheet

# Status-only car filters — prefer body-type category when known.
_CAR_STATUS_SLUGS = frozenset({"cars_new", "cars_used", "cars_bought"})

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILEAGE_RE = re.compile(
    r"(\d[\d\s\u00a0]{0,12})\s*(?:км|километр)",
    re.IGNORECASE,
)
HP_RE = re.compile(r"(\d+)\s*(?:л\.?\s*с\.?|лс|hp)\b", re.IGNORECASE)
PRICE_RE = re.compile(r"(\d[\d\s\u00a0]{2,16})\s*(?:₽|руб)", re.IGNORECASE)
DIGITS_RE = re.compile(r"\d+")

FIELD_ALIASES = {
    "title": ("название автомобиля", "название авто", "автомобиль", "название"),
    "brand": ("марка", "бренд", "производитель"),
    "model": ("модель", "комплектация автомобиля", "комплектация"),
    "year": ("год выпуска", "дата производства", "дата выпуска", "год"),
    "mileage": ("пробег", "наработка"),
    "horsepower": ("лошадиные силы", "мощность двигателя", "мощность"),
    "transmission": ("коробка передач", "трансмиссия", "коробка"),
    "body_type": ("тип кузова", "кузов автомобиля", "кузов"),
    "color": ("цвет кузова", "цвет"),
    "engine_type": (
        "тип двигателя",
        "тип топлива",
        "топливо",
        "двигатель",
        "fuel type",
        "fuel",
    ),
    "category": ("категория", "тип техники", "раздел"),
    "price_rub": ("цена под ключ", "цена", "стоимость"),
}

BODY_TO_SLUG = {
    "седан": "cars_sedan",
    "седаны": "cars_sedan",
    "кроссовер": "cars_crossover",
    "кроссоверы": "cars_crossover",
    "внедорожник": "cars_suv",
    "внедорожники": "cars_suv",
    "suv": "cars_suv",
    "минивэн": "cars_minivan",
    "минивен": "cars_minivan",
    "минивэны": "cars_minivan",
    "автовышка": "special_lifts",
    "автовышки": "special_lifts",
    "башенный кран": "special_cranes",
    "башенные краны": "special_cranes",
    "кран": "special_cranes",
    "грузовик": "trucks_trucks",
    "грузовики": "trucks_trucks",
    "фургон": "trucks_vans",
    "фургоны": "trucks_vans",
    "эвакуатор": "trucks_evac",
    "эвакуаторы": "trucks_evac",
}

PARENT_HINTS = (
    (("автовышк", "башенн", "кран", "спецтехник"), "special"),
    (("грузовик", "фургон", "эвакуатор", "кму", "коммерческ"), "trucks"),
)

MULTIWORD_BRANDS = (
    "mercedes-benz",
    "land rover",
    "great wall",
    "alfa romeo",
    "li auto",
    "li xiang",
    "hong qi",
)

MAX_GALLERY_UPLOADS = 80


@dataclass
class ListingData:
    title: str = ""
    brand_name: str = ""
    model: str = ""
    year: int = 0
    mileage: int = 0
    horsepower: int | None = None
    transmission: str = ""
    body_type: str = ""
    color: str = ""
    engine_type: str = ""
    category_name: str = ""
    price_rub: Decimal | None = None
    description: str = ""
    specs: dict = field(default_factory=dict)


@dataclass
class IngestResult:
    vehicle: Vehicle
    brand_created: bool
    category_created: bool
    photos_added: int = 0
    photos_skipped: int = 0


def _norm(value: str) -> str:
    return " ".join((value or "").lower().replace("ё", "е").split())


def _clean(value: str, limit: int = 255) -> str:
    return " ".join((value or "").split()).strip()[:limit]


def _int_from_grouped(value: str) -> int | None:
    digits = "".join(DIGITS_RE.findall(value or ""))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _year_from(value: str) -> int:
    match = YEAR_RE.search(value or "")
    return int(match.group(1)) if match else 0


def _mileage_from(value: str) -> int:
    match = MILEAGE_RE.search(value or "")
    raw = match.group(1) if match else value
    number = _int_from_grouped(raw or "")
    if number is None:
        return 0
    return min(number, 10_000_000)


def _horsepower_from(value: str) -> int | None:
    match = HP_RE.search(value or "")
    if match:
        return int(match.group(1))
    number = _int_from_grouped(value or "")
    if number is None or number > 2000:
        return None
    return number


def _price_from(value: str) -> Decimal | None:
    match = PRICE_RE.search(value or "")
    raw = match.group(1) if match else value
    number = _int_from_grouped(raw or "")
    if number is None or number <= 0:
        return None
    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def _pretty_color(value: str) -> str:
    text = _clean(value, 60)
    if not text:
        return ""
    return text[:1].upper() + text[1:]


def _lookup_spec(rows: dict[str, str], field: str) -> str:
    aliases = sorted(FIELD_ALIASES[field], key=len, reverse=True)
    for label, value in rows.items():
        normalized = _norm(label)
        for alias in aliases:
            if normalized == alias or normalized.startswith(alias):
                return value
    return ""


def _rows_as_map(raw: str) -> dict[str, str]:
    sheet = parse_spec_sheet(raw)
    mapped: dict[str, str] = {}
    for key, value in sheet.rows:
        if key and key not in mapped:
            mapped[key] = value
    return mapped


def _brand_from_title(title: str, existing: list[str]) -> str:
    lowered = _norm(title)
    if not lowered:
        return ""
    ranked = sorted(existing, key=len, reverse=True)
    for name in ranked:
        if lowered == _norm(name) or lowered.startswith(_norm(name) + " "):
            return name
    for prefix in MULTIWORD_BRANDS:
        if lowered.startswith(prefix):
            return title[: len(prefix)].strip() or prefix.title()
    return (title.split() or [""])[0]


def parse_listing_text(raw: str) -> ListingData:
    text = (raw or "").strip()
    rows = _rows_as_map(text)
    data = ListingData(description=text)

    data.title = _clean(_lookup_spec(rows, "title"))
    data.brand_name = _clean(_lookup_spec(rows, "brand"), 100)
    data.model = _clean(_lookup_spec(rows, "model"), 100)
    data.body_type = _clean(_lookup_spec(rows, "body_type"), 80)
    data.color = _pretty_color(_lookup_spec(rows, "color"))
    data.transmission = _clean(_lookup_spec(rows, "transmission"), 50)
    data.engine_type = detect_engine_type(_lookup_spec(rows, "engine_type"))
    data.category_name = _clean(_lookup_spec(rows, "category"), 100)

    year_raw = _lookup_spec(rows, "year")
    data.year = _year_from(year_raw) or _year_from(data.model) or _year_from(data.title)
    data.mileage = _mileage_from(_lookup_spec(rows, "mileage"))
    data.horsepower = _horsepower_from(_lookup_spec(rows, "horsepower")) or None
    data.price_rub = _price_from(_lookup_spec(rows, "price_rub"))

    if not data.brand_name:
        existing = list(Brand.objects.values_list("name", flat=True))
        source = data.title or text.split("\n", 1)[0]
        data.brand_name = _clean(_brand_from_title(source, existing), 100)

    if not data.title:
        bits = [data.brand_name, data.model, str(data.year or "")]
        data.title = _clean(" ".join(bit for bit in bits if bit)) or "Автомобиль"

    return data


def unique_slug(model, base: str) -> str:
    slug = slugify(unidecode(base)) or "item"
    candidate = slug
    index = 1
    while model.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{index}"
        index += 1
    return candidate


def get_or_create_brand(name: str) -> tuple[Brand, bool]:
    cleaned = _clean(name, 100) or "Unknown"
    existing = Brand.objects.filter(name__iexact=cleaned).first()
    if existing:
        return existing, False
    return (
        Brand.objects.create(name=cleaned, slug=unique_slug(Brand, cleaned)),
        True,
    )


def _ensure_root(slug: str, name: str) -> Category:
    obj, _created = Category.objects.get_or_create(
        slug=slug, defaults={"name": name, "parent": None}
    )
    return obj


def _parent_for(name: str, body_type: str, haystack: str) -> Category:
    blob = _norm(" ".join((name, body_type, haystack)))
    for needles, slug in PARENT_HINTS:
        if any(needle in blob for needle in needles):
            if slug == "special":
                return _ensure_root("special", "Спецтехника")
            return _ensure_root("trucks", "Коммерческий транспорт")
    return _ensure_root("cars", "Легковые автомобили")


def _match_existing_category(name: str) -> Category | None:
    cleaned = _clean(name, 100)
    if not cleaned:
        return None
    by_name = Category.objects.filter(name__iexact=cleaned).first()
    if by_name:
        return by_name
    slug = slugify(unidecode(cleaned))
    if slug:
        by_slug = Category.objects.filter(slug=slug).first()
        if by_slug:
            return by_slug
    mapped = BODY_TO_SLUG.get(_norm(cleaned))
    if mapped:
        return Category.objects.filter(slug=mapped).first()
    return None


def get_or_create_category(
    name: str,
    *,
    body_type: str = "",
    haystack: str = "",
    mileage: int = 0,
    explicit: Category | None = None,
) -> tuple[Category, bool]:
    if explicit is not None:
        return explicit, False

    body_mapped = BODY_TO_SLUG.get(_norm(body_type)) or BODY_TO_SLUG.get(_norm(name))
    if body_mapped:
        existing = Category.objects.filter(slug=body_mapped).first()
        if existing:
            return existing, False

    matched = _match_existing_category(name) or _match_existing_category(body_type)
    if matched:
        # Don't park the car only under «Выкупленные»/«Новые» when body type is known.
        if matched.slug in _CAR_STATUS_SLUGS:
            mapped = BODY_TO_SLUG.get(_norm(body_type))
            if mapped:
                body_cat = Category.objects.filter(slug=mapped).first()
                if body_cat:
                    return body_cat, False
        return matched, False

    blob = _norm(" ".join((name, body_type, haystack)))
    if name:
        parent = _parent_for(name, body_type, haystack)
        created = Category.objects.create(
            name=_clean(name, 100),
            slug=unique_slug(Category, name),
            parent=parent,
        )
        return created, True

    # Status words are flags (is_featured / is_new), not exclusive categories.
    if mileage == 0 and "выкуплен" not in blob:
        new_cat = Category.objects.filter(slug="cars_new").first()
        if new_cat:
            return new_cat, False
    used = Category.objects.filter(slug="cars_used").first()
    if used:
        return used, False
    fallback = Category.objects.filter(slug="cars").first()
    if fallback:
        return fallback, False
    return _ensure_root("cars", "Легковые автомобили"), False


def _listing_looks_bought(name: str, body_type: str, haystack: str) -> bool:
    return "выкуплен" in _norm(" ".join((name, body_type, haystack)))


def attach_vehicle_images(vehicle: Vehicle, uploads) -> tuple[int, int]:
    files = []
    if uploads:
        if isinstance(uploads, (list, tuple)):
            files = list(uploads)
        else:
            files = [uploads]
    files = [item for item in files if item][:MAX_GALLERY_UPLOADS]
    if not files:
        return 0, 0

    max_order = vehicle.gallery.aggregate(max_order=Max("order")).get("max_order") or 0
    added = 0
    skipped = 0
    for index, image in enumerate(files, start=1):
        raw = _read_upload(image)
        if raw is None:
            skipped += 1
            continue
        VehicleImage.objects.create(
            vehicle=vehicle,
            image=image,
            order=max_order + index,
        )
        added += 1

    vehicle.refresh_from_db()
    if added and not vehicle.main_image:
        first = vehicle.gallery.order_by("order", "id").first()
        if first and first.image:
            vehicle.main_image = first.image
            vehicle.save(update_fields=["main_image"])
    return added, skipped


def _read_upload(image: UploadedFile) -> bytes | None:
    try:
        raw = image.read()
        image.seek(0)
        probe = Image.open(BytesIO(raw))
        probe.verify()
        image.seek(0)
        return raw
    except Exception:
        return None


def ingest_listing(
    raw: str,
    *,
    uploads=None,
    category: Category | None = None,
) -> IngestResult:
    data = parse_listing_text(raw)
    brand, brand_created = get_or_create_brand(data.brand_name)
    resolved_category, category_created = get_or_create_category(
        data.category_name,
        body_type=data.body_type,
        haystack=data.description,
        mileage=data.mileage,
        explicit=category,
    )
    looks_bought = _listing_looks_bought(
        data.category_name, data.body_type, data.description
    ) or getattr(resolved_category, "slug", None) == "cars_bought"
    vehicle = Vehicle.objects.create(
        title=data.title[:255],
        brand=brand,
        category=resolved_category,
        model=data.model,
        year=data.year or 0,
        mileage=data.mileage,
        horsepower=data.horsepower,
        transmission=data.transmission,
        body_type=data.body_type,
        color=data.color,
        engine_type=data.engine_type,
        price_rub=data.price_rub,
        description=data.description,
        specs=data.specs,
        is_published=False,
        is_new=getattr(resolved_category, "slug", None) == "cars_new",
        is_featured=looks_bought,
    )
    added, skipped = attach_vehicle_images(vehicle, uploads)
    vehicle.refresh_from_db()
    return IngestResult(
        vehicle=vehicle,
        brand_created=brand_created,
        category_created=category_created,
        photos_added=added,
        photos_skipped=skipped,
    )
