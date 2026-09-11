"""Cached catalog navigation fragments and color facets."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from django.core.cache import cache
from django.db.models import Avg, Count, Q

from content.faq_defaults import HOME_FAQ_PREVIEW

from .models import Brand, Category, Vehicle

COLORS_CACHE_KEY = "catalog:available_colors"
NAV_CACHE_KEY = "catalog:nav_context"
HOME_SECTIONS_CACHE_KEY = "catalog:home_sections"
HOME_SECTIONS_VER_KEY = "catalog:home_sections:ver"
HOME_REVIEWS_CACHE_KEY = "catalog:home_reviews"
HOME_REVIEWS_VER_KEY = "catalog:home_reviews:ver"
REVIEW_PLATFORMS_CACHE_KEY = "catalog:review_platforms"
REVIEW_AGGREGATE_CACHE_KEY = "catalog:review_aggregate"
SEO_BRANDS_CACHE_KEY = "catalog:seo_brands"
CACHE_TTL = 300
NAV_CACHE_TTL = 600
HOME_SECTION_LIMIT = 10

# Special car filters — not body-type options in search dropdowns
CAR_STATUS_SLUGS = ("cars_new", "cars_used", "cars_bought")
_CAR_SPECIAL_SLUGS = CAR_STATUS_SLUGS
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

T = TypeVar("T")


def cache_get_or_set(
    key: str,
    builder: Callable[[], T],
    ttl: int = CACHE_TTL,
    *,
    lock_ttl: int = 8,
) -> T:
    """
    Fetch-or-build with a short lock so concurrent misses don't stampede the DB.
    Lock losers wait briefly for the winner's value, then build as a last resort.
    """
    cached = cache.get(key)
    if cached is not None:
        return cached

    lock_key = f"{key}:lock"
    if cache.add(lock_key, 1, timeout=lock_ttl):
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
            data = builder()
            cache.set(key, data, ttl)
            return data
        finally:
            cache.delete(lock_key)

    for _ in range(40):
        time.sleep(0.05)
        cached = cache.get(key)
        if cached is not None:
            return cached
    return builder()


def _cache_version(key: str) -> int:
    try:
        return int(cache.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _bump_version(key: str) -> None:
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, None)


def category_name_match_terms(category: Category) -> set[str]:
    """Singular/plural name variants for body_type text matching."""
    name = (category.name or "").strip()
    if not name:
        return set()
    terms = {name}
    # "Седаны" -> "Седан", "Минивэны" -> "Минивэн".
    if name[-1:].lower() in {"ы", "и"}:
        singular = name[:-1].strip()
        if singular:
            terms.add(singular)
    terms |= {term.lower() for term in terms}
    return terms


def type_category_q(category: Category) -> Q:
    """
    Match vehicles by category tree OR body_type text.

    Status categories (Новые / Выкупленные) keep a single FK; body-type pages
    still need those cars when body_type is filled (e.g. Кроссовер).
    """
    q = Q(category_id__in=category.subtree_ids())
    for term in category_name_match_terms(category):
        q |= Q(body_type__icontains=term)
    return q


def is_car_body_type_category(category: Category) -> bool:
    parent = getattr(category, "parent", None)
    if parent is None or getattr(parent, "slug", None) != "cars":
        return False
    return category.slug not in CAR_STATUS_SLUGS


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
    cache.delete(SEO_BRANDS_CACHE_KEY)


def invalidate_subtree_cache() -> None:
    try:
        cache.incr("catalog:subtree_gen")
    except ValueError:
        cache.set("catalog:subtree_gen", 1)


def invalidate_home_sections_cache() -> None:
    _bump_version(HOME_SECTIONS_VER_KEY)


def invalidate_vehicle_public_caches() -> None:
    """Call after QuerySet.update() which skips model signals."""
    invalidate_colors_cache()
    invalidate_nav_cache()
    invalidate_home_sections_cache()


def invalidate_home_faqs_cache() -> None:
    """No-op: home FAQ is static. Kept for import compatibility."""
    return None


def invalidate_home_reviews_cache() -> None:
    _bump_version(HOME_REVIEWS_VER_KEY)
    cache.delete(REVIEW_PLATFORMS_CACHE_KEY)
    cache.delete(REVIEW_AGGREGATE_CACHE_KEY)


def available_colors() -> list[str]:
    """
    Distinct non-empty colors from published vehicles (normalized `color` field).
    Cached for CACHE_TTL seconds.
    """

    def build() -> list[str]:
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
        return result

    return cache_get_or_set(COLORS_CACHE_KEY, build, CACHE_TTL)


def nav_context() -> dict:
    """Brands and category lists shared by home + catalog list."""

    def build() -> dict:
        return {
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

    return cache_get_or_set(NAV_CACHE_KEY, build, NAV_CACHE_TTL)


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
        .defer("description", "specs")
        .order_by("-created_at")[:limit]
    )


def home_sections(limit: int = HOME_SECTION_LIMIT) -> dict:
    """Published homepage vehicles for the three carousels."""
    ver = _cache_version(HOME_SECTIONS_VER_KEY)
    cache_key = f"{HOME_SECTIONS_CACHE_KEY}:v{ver}:{limit}"

    def build() -> dict:
        return {
            "home_cars": _section_vehicles("cars", limit),
            "home_trucks": _section_vehicles("trucks", limit),
            "home_special": _section_vehicles("special", limit),
        }

    return cache_get_or_set(cache_key, build, CACHE_TTL)


def home_faqs() -> list[dict]:
    """FAQ для главной: статический список из faq_defaults (не БД)."""
    return list(HOME_FAQ_PREVIEW)


def home_reviews(limit: int = 6) -> list:
    """Опубликованные отзывы с 2ГИС / Авито / Яндекс Карт для главной."""
    from content.models import Review

    ver = _cache_version(HOME_REVIEWS_VER_KEY)
    cache_key = f"{HOME_REVIEWS_CACHE_KEY}:v{ver}:{limit}"

    def build() -> list:
        return list(
            Review.objects.filter(is_published=True).order_by("order", "-date")[:limit]
        )

    return cache_get_or_set(cache_key, build, CACHE_TTL)


def review_aggregate() -> dict | None:
    """Average rating across published reviews for JSON-LD AggregateRating."""
    from content.models import Review

    def build() -> dict:
        stats = Review.objects.filter(is_published=True).aggregate(
            count=Count("id"), avg=Avg("rating")
        )
        count = int(stats["count"] or 0)
        if count <= 0 or stats["avg"] is None:
            return {}
        return {
            "ratingValue": round(float(stats["avg"]), 1),
            "reviewCount": count,
        }

    try:
        payload = cache_get_or_set(REVIEW_AGGREGATE_CACHE_KEY, build, CACHE_TTL)
    except Exception:
        payload = build()
    return payload or None


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

    Рейтинг/число оценок — из админки («Ссылки на отзывы»), если заданы;
    иначе считаются по опубликованным Review в БД.
    URL площадки — из админки, иначе из .env.
    """
    from content.models import Review, ReviewPlatformSettings, platform_url_for_source

    def build() -> list[dict]:
        settings_obj = ReviewPlatformSettings.load()
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
            manual_avg, manual_count = settings_obj.rating_for_source(item["source"])
            if manual_count is not None:
                count = manual_count
                avg = manual_avg
            else:
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
            item["label"] = f"{item['name']} · {item['count_label']}"
        return platforms

    return cache_get_or_set(REVIEW_PLATFORMS_CACHE_KEY, build, CACHE_TTL)


def seo_brands_cached() -> list:
    """Cached brand directory for /catalog/brands/."""
    from .seo_pages import seo_brands_queryset

    return cache_get_or_set(
        SEO_BRANDS_CACHE_KEY,
        lambda: list(seo_brands_queryset()),
        CACHE_TTL,
    )
