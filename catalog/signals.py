from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from content.models import Review

from .cache_helpers import (
    invalidate_colors_cache,
    invalidate_home_reviews_cache,
    invalidate_home_sections_cache,
    invalidate_nav_cache,
    invalidate_subtree_cache,
)
from .models import Brand, Category, Vehicle

# Stash previous price_rub on the instance for post_save comparison.
_AVITO_PRICE_ATTR = "_avito_prev_price_rub"


def _prices_differ(old, new) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return Decimal(old) != Decimal(new)


def enqueue_avito_price_sync(vehicle_id: int) -> None:
    """Fire Celery task when Avito credentials exist; no-op otherwise."""
    from .avito import is_configured
    from .tasks import sync_avito_price_task

    if not is_configured():
        return
    sync_avito_price_task.delay(vehicle_id)


@receiver(pre_save, sender=Vehicle)
def vehicle_remember_price_for_avito(sender, instance: Vehicle, **kwargs):
    if not instance.pk:
        setattr(instance, _AVITO_PRICE_ATTR, None)
        return
    prev = (
        Vehicle.objects.filter(pk=instance.pk)
        .values_list("price_rub", flat=True)
        .first()
    )
    setattr(instance, _AVITO_PRICE_ATTR, prev)


@receiver(post_save, sender=Vehicle)
def vehicle_enqueue_avito_price_sync(sender, instance: Vehicle, created, **kwargs):
    if not instance.avito_item_id:
        return
    if instance.price_rub is None:
        return
    prev = getattr(instance, _AVITO_PRICE_ATTR, None)
    # New vehicle with price + avito id, or price changed.
    if created or _prices_differ(prev, instance.price_rub):
        enqueue_avito_price_sync(instance.pk)


@receiver([post_save, post_delete], sender=Vehicle)
def vehicle_cache_invalidation(sender, **kwargs):
    invalidate_colors_cache()
    invalidate_nav_cache()
    invalidate_home_sections_cache()


@receiver([post_save, post_delete], sender=Brand)
def brand_cache_invalidation(sender, **kwargs):
    invalidate_nav_cache()
    invalidate_home_sections_cache()


@receiver([post_save, post_delete], sender=Category)
def category_cache_invalidation(sender, **kwargs):
    invalidate_nav_cache()
    invalidate_home_sections_cache()
    invalidate_subtree_cache()


@receiver([post_save, post_delete], sender=Review)
def review_cache_invalidation(sender, **kwargs):
    invalidate_home_reviews_cache()
