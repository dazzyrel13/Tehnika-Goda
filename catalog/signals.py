from django.db.models.signals import post_delete, post_save
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
