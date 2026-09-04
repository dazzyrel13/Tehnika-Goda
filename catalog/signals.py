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

# Stash previous price / avito id on the instance for post_save comparison.
_AVITO_PRICE_ATTR = "_avito_prev_price_rub"
_AVITO_ITEM_ATTR = "_avito_prev_item_id"


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
        setattr(instance, _AVITO_ITEM_ATTR, None)
        return
    prev = (
        Vehicle.objects.filter(pk=instance.pk)
        .values_list("price_rub", "avito_item_id")
        .first()
    )
    if prev is None:
        setattr(instance, _AVITO_PRICE_ATTR, None)
        setattr(instance, _AVITO_ITEM_ATTR, None)
        return
    setattr(instance, _AVITO_PRICE_ATTR, prev[0])
    setattr(instance, _AVITO_ITEM_ATTR, prev[1])


@receiver(post_save, sender=Vehicle)
def vehicle_enqueue_avito_price_sync(sender, instance: Vehicle, created, **kwargs):
    if not instance.avito_item_id:
        return
    if instance.price_rub is None:
        return
    prev_price = getattr(instance, _AVITO_PRICE_ATTR, None)
    prev_item = getattr(instance, _AVITO_ITEM_ATTR, None)
    price_changed = created or _prices_differ(prev_price, instance.price_rub)
    # First link (or re-link) to an Avito listing should push current site price.
    item_linked = created or prev_item != instance.avito_item_id
    if price_changed or item_linked:
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
