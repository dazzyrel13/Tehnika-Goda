from django.core.cache import cache

from content.models import PromoBanner


def home_promos(limit: int = 8) -> list[PromoBanner]:
    """Опубликованные акции для блока на главной."""

    def build() -> list[PromoBanner]:
        return list(
            PromoBanner.objects.filter(is_published=True).order_by(
                "sort_order", "-updated_at"
            )[:limit]
        )

    try:
        cached = cache.get("content:home_promos")
    except Exception:
        cached = None
    if cached is not None:
        return list(cached)[:limit]
    items = build()
    try:
        cache.set("content:home_promos", items, 60 * 10)
    except Exception:
        pass
    return items
