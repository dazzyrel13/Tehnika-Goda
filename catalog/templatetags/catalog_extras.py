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
    Плашки карточки: «Новый» (0 км), «Выкупленные» (флаг/категория),
    либо кастомный badge_text.
    """
    items = []
    if getattr(vehicle, "mileage", None) == 0:
        items.append({"text": "Новый", "class": "badge-new"})

    category = getattr(vehicle, "category", None)
    is_bought = bool(getattr(vehicle, "is_featured", False)) or (
        getattr(category, "slug", None) == "cars_bought"
    )
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
    images = []
    seen = set()
    cover = getattr(vehicle, "main_image", None)
    cover_name = (getattr(cover, "name", None) or "").strip()
    if cover_name:
        images.append(cover)
        seen.add(cover_name)
    gallery = getattr(vehicle, "gallery", None)
    items = gallery.all() if gallery is not None else []
    for item in items:
        photo = getattr(item, "image", None)
        name = (getattr(photo, "name", None) or "").strip()
        if name and name not in seen:
            images.append(photo)
            seen.add(name)
    return images
