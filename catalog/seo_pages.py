"""SEO model landing pages — helpers and feature flag."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Q, QuerySet

from .models import Brand, CarModel, Vehicle


def seo_model_pages_enabled() -> bool:
    return bool(getattr(settings, "SEO_MODEL_PAGES_ENABLED", False))


def car_model_vehicle_filter(car_model: CarModel) -> Q:
    """Match published vehicles for a CarModel row."""
    name = (car_model.name or "").strip()
    if not name:
        return Q(pk__in=[])
    return Q(brand_id=car_model.brand_id) & (
        Q(model__iexact=name)
        | Q(model__icontains=name)
        | Q(title__icontains=name)
    )


def vehicles_for_car_model(car_model: CarModel) -> QuerySet:
    return (
        Vehicle.objects.filter(is_published=True)
        .filter(car_model_vehicle_filter(car_model))
        .select_related("brand", "category")
        .order_by("-is_featured", "-created_at")
    )


def seo_brands_queryset() -> QuerySet:
    """Brands on /catalog/brands/ and in the brands sitemap."""
    return (
        Brand.objects.filter(
            Q(seo_landing_enabled=True)
            | Q(car_models__is_published=True)
            | Q(vehicles__is_published=True)
        )
        .distinct()
        .order_by("name")
    )


def brand_has_seo_landing(brand: Brand) -> bool:
    """Whether the brand page is meant to be public for SEO (with or without stock)."""
    if brand.seo_landing_enabled:
        return True
    if brand.car_models.filter(is_published=True).exists():
        return True
    return brand.vehicles.filter(is_published=True).exists()


def published_car_models_for_brand(brand: Brand) -> QuerySet:
    return brand.car_models.filter(is_published=True).order_by("sort_order", "name")
