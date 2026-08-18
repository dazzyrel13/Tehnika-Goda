"""Cached catalog navigation fragments and color facets."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Avg, Count, Q

from content.faq_defaults import HOME_FAQ_PREVIEW

from .models import Brand, Category, Vehicle

COLORS_CACHE_KEY = "catalog:available_colors"
NAV_CACHE_KEY = "catalog:nav_context"
HOME_SECTIONS_CACHE_KEY = "catalog:home_sections"
HOME_REVIEWS_CACHE_KEY = "catalog:home_reviews"
REVIEW_PLATFORMS_CACHE_KEY = "catalog:review_platforms"
CACHE_TTL = 300
HOME_SECTION_LIMIT = 10

# Special car filters — not body-type options in search dropdowns
_CAR_SPECIAL_SLUGS = ("cars_new", "cars_used", "cars_bought")
_TRUCK_TYPE_SLUGS = (
    "trucks_trucks",
    "trucks_vans",
    "trucks_km",
    "trucks_evac",
)
_SPECIAL_TYPE_SLUGS = (
    "special_lifts",
    "special_cranes",
)


def _ordered_children(
    parent_slug: str, preferred_slugs: tuple[str, ...], *, include_extras: bool = True
) -> list:
    children = list(Category.objects.filter(parent__slug=parent_slug))
    by_slug = {cat.slug: cat for cat in children}
    result = []
    seen: set[str] = set()
    for slug in preferred_slugs:
        obj = by_slug.get(slug)
        if obj:
            result.append(obj)
            seen.add(slug)
    if include_extras:
        extras = [cat for cat in children if cat.slug not in seen]
        extras.sort(key=lambda cat: cat.name)
        result.extend(extras)
    return result


def _brands_in_tree(root_slug: str) -> list:
    root = Category.objects.filter(slug=root_slug).first()
    if not root:
        return []
    return list(
        Brand.objects.filter(
            vehicles__is_published=True,
            vehicles__category_id__in=root.subtree_ids(),
        )
        .distinct()
        .order_by("name")
    )


def invalidate_colors_cache() -> None:
    cache.delete(COLORS_CACHE_KEY)


def invalidate_nav_cache() -> None:
    cache.delete(NAV_CACHE_KEY)


def invalidate_subtree_cache() -> None:
    try:
        cache.incr("catalog:subtree_gen")
    except ValueError:
        cache.set("catalog:subtree_gen", 1)


def invalidate_home_sections_cache() -> None:
    cache.delete(f"{HOME_SECTIONS_CACHE_KEY}:{HOME_SECTION_LIMIT}")


def invalidate_vehicle_public_caches() -> None:
    """Call after QuerySet.update() which skips model signals."""
    invalidate_colors_cache()
    invalidate_nav_cache()
    invalidate_home_sections_cache()


def invalidate_home_faqs_cache() -> None:
    """No-op: home FAQ is static. Kept for import compatibility."""
    return None


def invalidate_home_reviews_cache() -> None:
    cache.delete(HOME_REVIEWS_CACHE_KEY)
    cache.delete(REVIEW_PLATFORMS_CACHE_KEY)
    cache.delete("catalog:review_aggregate")


def available_colors() -> list[str]:
    """
    Distinct non-empty colors from published vehicles (normalized `color` field).
    Cached for CACHE_TTL seconds.
    """
    cached = cache.get(COLORS_CACHE_KEY)
    if cached is not None:
        return cached

    colors = list(
        Vehicle.objects.filter(is_published=True)
        .exclude(color="")
        .exclude(color__isnull=True)
        .values_list("color", flat=True)
        .distinct()
        .order_by("color")
    )
    seen: set[str] = set()
    result: list[str] = []
    for raw in colors:
        value = str(raw).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)

    cache.set(COLORS_CACHE_KEY, result, CACHE_TTL)
    return result


def nav_context() -> dict:
    """Brands and category lists shared by home + catalog list."""
    cached = cache.get(NAV_CACHE_KEY)
    if cached is not None:
        return cached

    data = {
        "brands": list(Brand.objects.all()),
        "main_categories": list(Category.objects.filter(parent=None)),
        "car_type_categories": list(
            Category.objects.filter(parent__slug="cars")
            .exclude(slug__in=_CAR_SPECIAL_SLUGS)
            .exclude(slug="sedan")
            .exclude(
                Q(name__icontains="нов")
                | Q(name__icontains="пробег")
                | Q(name__icontains="выкупл")
            )
            .order_by("name")
        ),
        "truck_type_categories": _ordered_children("trucks", _TRUCK_TYPE_SLUGS),
        "special_type_categories": _ordered_children(
            "special", _SPECIAL_TYPE_SLUGS, include_extras=False
        ),
        "car_brands": _brands_in_tree("cars"),
        "truck_brands": _brands_in_tree("trucks"),
        "special_brands": _brands_in_tree("special"),
    }
    cache.set(NAV_CACHE_KEY, data, CACHE_TTL)
    return data


def _section_vehicles(root_slug: str, limit: int) -> list:
    root = Category.objects.filter(slug=root_slug).first()
    if not root:
        return []
    return list(
        Vehicle.objects.filter(
            is_published=True,
            show_on_home=True,
            category_id__in=root.subtree_ids(),
        )
        .select_related("brand", "category")
        .order_by("-is_featured", "-created_at")[:limit]
    )


def home_sections(limit: int = HOME_SECTION_LIMIT) -> dict:
    """Published homepage vehicles for the three carousels."""
    cache_key = f"{HOME_SECTIONS_CACHE_KEY}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    data = {
        "home_cars": _section_vehicles("cars", limit),
        "home_trucks": _section_vehicles("trucks", limit),
        "home_special": _section_vehicles("special", limit),
    }
    cache.set(cache_key, data, CACHE_TTL)
    return data


def home_faqs() -> list[dict]:
    """FAQ для главной: статический список из faq_defaults (не БД)."""
    return list(HOME_FAQ_PREVIEW)


def home_reviews(limit: int = 6) -> list:
    """Опубликованные отзывы с 2ГИС / Авито / Яндекс Карт для главной."""
    from content.models import Review

    cached = cache.get(HOME_REVIEWS_CACHE_KEY)
    if cached is not None:
        return cached

    result = list(
        Review.objects.filter(is_published=True).order_by("order", "-date")[:limit]
    )
    cache.set(HOME_REVIEWS_CACHE_KEY, result, CACHE_TTL)
    return result


def review_aggregate() -> dict | None:
    """Average rating across published reviews for JSON-LD AggregateRating."""
    from content.models import Review

    cache_key = "catalog:review_aggregate"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    stats = Review.objects.filter(is_published=True).aggregate(
        count=Count("id"), avg=Avg("rating")
    )
    count = int(stats["count"] or 0)
    if count <= 0 or stats["avg"] is None:
        cache.set(cache_key, {}, CACHE_TTL)
        return None
    payload = {
        "ratingValue": round(float(stats["avg"]), 1),
        "reviewCount": count,
    }
    cache.set(cache_key, payload, CACHE_TTL)
    return payload


def _reviews_count_label(count: int) -> str:
    """Russian pluralization for rating counts."""
    if count <= 0:
        return "пока нет оценок"
    n = abs(count) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        word = "оценок"
    elif n1 == 1:
        word = "оценка"
    elif 2 <= n1 <= 4:
        word = "оценки"
    else:
        word = "оценок"
    return f"{count} {word}"


def review_platforms() -> list[dict]:
    """
    Виджеты рейтингов площадок для главной.

    Score/count считаются по опубликованным Review в БД.
    URL площадки — из админки («Ссылки на отзывы»), иначе из .env.
    """
    from content.models import Review, platform_url_for_source

    cached = cache.get(REVIEW_PLATFORMS_CACHE_KEY)
    if cached is not None:
        return cached

    stats = {
        row["source"]: row
        for row in Review.objects.filter(is_published=True)
        .values("source")
        .annotate(count=Count("id"), avg=Avg("rating"))
    }

    platforms = [
        {
            "key": "yandex",
            "source": Review.SOURCE_YANDEX,
            "name": "Яндекс Карты",
            "icon": "images/brands/yandex-maps.png",
            "url": platform_url_for_source("yandex"),
            "caption": "Рейтинг в Яндекс Картах",
        },
        {
            "key": "2gis",
            "source": Review.SOURCE_2GIS,
            "name": "2ГИС",
            "icon": "images/brands/2gis.png",
            "url": platform_url_for_source("2gis"),
            "caption": "Рейтинг в 2ГИС",
        },
        {
            "key": "avito",
            "source": Review.SOURCE_AVITO,
            "name": "Авито",
            "icon": "images/brands/avito.png",
            "url": platform_url_for_source("avito"),
            "caption": "Рейтинг на Авито",
        },
    ]

    for item in platforms:
        row = stats.get(item["source"]) or {}
        count = int(row.get("count") or 0)
        avg = row.get("avg")
        item["count"] = count
        if count > 0 and avg is not None:
            item["score"] = f"{float(avg):.1f}"
            item["has_rating"] = True
        else:
            item["score"] = "—"
            item["has_rating"] = False
        item["count_label"] = _reviews_count_label(count)
        item["label"] = f"{item['caption']} · {item['count_label']}"

    cache.set(REVIEW_PLATFORMS_CACHE_KEY, platforms, CACHE_TTL)
    return platforms
