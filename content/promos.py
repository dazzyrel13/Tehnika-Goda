"""Home promo banners: query + default seed from data/promos."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.files import File

from content.models import PromoBanner

DEFAULT_PROMOS = (
    {
        "file": "credit.webp",
        "title": "Авто в кредит",
        "teaser": "Выгодные условия и быстрое одобрение. Автомобили под заказ из Китая.",
        "sort_order": 10,
    },
    {
        "file": "winter-tires.jpg",
        "title": "Зимние шины в подарок",
        "teaser": "При заказе авто до 30 сентября — комплект зимней резины бесплатно.",
        "sort_order": 20,
    },
)

CACHE_KEY = "content:home_promos"


def invalidate_home_promos_cache() -> None:
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        pass


def home_promos(limit: int = 8) -> list[PromoBanner]:
    """Опубликованные акции для блока на главной."""

    def build() -> list[PromoBanner]:
        return list(
            PromoBanner.objects.filter(is_published=True).order_by(
                "sort_order", "-updated_at"
            )[:limit]
        )

    try:
        cached = cache.get(CACHE_KEY)
    except Exception:
        cached = None
    if cached is not None:
        return list(cached)[:limit]
    items = build()
    try:
        cache.set(CACHE_KEY, items, 60 * 10)
    except Exception:
        pass
    return items


def resync_default_promos(*, replace_all: bool = False) -> int:
    """
    Ensure the two default banners exist with clean assets from data/promos.

    If replace_all=True, delete every PromoBanner first (fixes duplicates / screenshots).
    """
    base = Path(settings.BASE_DIR) / "data" / "promos"
    if replace_all:
        for obj in PromoBanner.objects.all():
            obj.delete()

    kept_titles = {row["title"] for row in DEFAULT_PROMOS}
    # Drop leftover duplicates of the same titles before recreate
    for title in kept_titles:
        qs = PromoBanner.objects.filter(title=title).order_by("pk")
        for extra in qs[1:]:
            extra.delete()

    created_or_updated = 0
    for seed in DEFAULT_PROMOS:
        path = base / seed["file"]
        if not path.exists():
            continue
        banner = PromoBanner.objects.filter(title=seed["title"]).first()
        if banner is None:
            banner = PromoBanner(title=seed["title"])
        banner.teaser = seed["teaser"]
        banner.link_url = "#leads-section"
        banner.is_published = True
        banner.sort_order = seed["sort_order"]
        with path.open("rb") as fh:
            banner.image.save(path.name, File(fh), save=False)
        banner.save()
        created_or_updated += 1

    # Remove other published junk titles if we are doing a full reset
    if replace_all:
        PromoBanner.objects.exclude(title__in=kept_titles).delete()

    invalidate_home_promos_cache()
    return created_or_updated
