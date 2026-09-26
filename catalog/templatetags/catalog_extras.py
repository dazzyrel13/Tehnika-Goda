import re

from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.safestring import mark_safe

from utils.html_sanitize import sanitize_html
from utils.image_processing import responsive_attrs

register = template.Library()


@register.filter
def strip_year_suffix(value):
    """
    Removes common year suffixes from vehicle titles, for example:
    - "Model X (2021)"
    - "Model X (октябрь 2021)"
    - "Model X 2021"
    """
    text = str(value or "").strip()
    if not text:
        return text

    text = re.sub(r"\s*\([^)]*\b\d{4}\b[^)]*\)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\b\d{4}\b\s*$", "", text)
    return text.strip()


@register.filter
def price_rub_display(value):
    """Форматирует цену в ₽ или «Цена по запросу»."""
    if value is None or value == "":
        return "Цена по запросу"
    try:
        return f"{intcomma(int(value))} ₽"
    except (TypeError, ValueError):
        return "Цена по запросу"


@register.filter
def mileage_display(value):
    """Форматирует пробег: 30000 → «30 000 км»."""
    if value is None or value == "":
        return "уточняется"
    try:
        grouped = f"{int(value):,}".replace(",", " ")
        return f"{grouped} км"
    except (TypeError, ValueError):
        return "уточняется"


@register.filter
def sanitized_html(value):
    """Always re-sanitize HTML before |safe rendering (defense in depth)."""
    if not value:
        return ""
    return mark_safe(sanitize_html(str(value)))


@register.simple_tag
def vehicle_badge_items(vehicle):
    """
    Плашки карточки: «Новые» (категория), «Выкупленные» (флаг/категория),
    либо кастомный badge_text.
    """
    items = []
    category = getattr(vehicle, "category", None)
    cat_slug = getattr(category, "slug", None)

    if getattr(vehicle, "is_new", False) or cat_slug == "cars_new":
        items.append({"text": "Новые", "class": "badge-new-category"})

    is_bought = bool(getattr(vehicle, "is_featured", False)) or cat_slug == "cars_bought"
    if is_bought:
        items.append({"text": "Выкупленные", "class": "badge-featured"})
    elif (getattr(vehicle, "badge_text", None) or "").strip():
        items.append({"text": vehicle.badge_text.strip(), "class": "badge-red"})
    return items


@register.simple_tag
def responsive_image(image_field, default_width=800):
    """src / srcset / full_src for a stored ImageField (variants if present)."""
    try:
        width = int(default_width)
    except (TypeError, ValueError):
        width = 800
    return responsive_attrs(image_field, default_width=width)


@register.simple_tag
def vehicle_gallery_images(vehicle):
    """Cover first, then unique gallery photos (cover is stored separately)."""
    import hashlib

    images = []
    seen = set()
    fingerprints = set()

    def fingerprint(field):
        """Identify copied files even when their storage names differ."""
        try:
            field.open("rb")
            digest = hashlib.sha256(field.read()).hexdigest()
            field.close()
            return digest
        except Exception:
            try:
                field.close()
            except Exception:
                pass
            return None

    cover = getattr(vehicle, "main_image", None)
    cover_name = (getattr(cover, "name", None) or "").strip()
    if cover_name:
        images.append(cover)
        seen.add(cover_name)
        cover_fingerprint = fingerprint(cover)
        if cover_fingerprint:
            fingerprints.add(cover_fingerprint)
    gallery = getattr(vehicle, "gallery", None)
    items = gallery.all() if gallery is not None else []
    for item in items:
        photo = getattr(item, "image", None)
        name = (getattr(photo, "name", None) or "").strip()
        photo_fingerprint = fingerprint(photo) if name else None
        if (
            name
            and name not in seen
            and (not photo_fingerprint or photo_fingerprint not in fingerprints)
        ):
            images.append(photo)
            seen.add(name)
            if photo_fingerprint:
                fingerprints.add(photo_fingerprint)
    return images
