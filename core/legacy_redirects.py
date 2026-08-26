"""301 redirects from the old WordPress / WooCommerce site."""

from __future__ import annotations

import re

from django.http import HttpResponsePermanentRedirect
from django.urls import path, re_path, reverse
from django.views.generic import RedirectView


# Old WooCommerce product slug → new vehicle slug or category fallback.
LEGACY_PRODUCT_SLUGS: dict[str, str] = {
    "audi-q3": "vehicle:audi-q3",
    "honda-vezel-2021": "vehicle:honda-vezel",
    "toyota-levin-2022-god": "category:cars",
    "honda-c-rv-2023": "category:cars",
    "автовышка-isuzu-elf-n-series-30m": "category:special_lifts",
    "автовышка-isuzu-giga-45m": "category:special_lifts",
    "грузовой-фургон-dodge-ram": "category:trucks",
}

# Old /бренд/<slug>/ → catalog brand slug (or cars if unknown).
LEGACY_BRAND_SLUGS: dict[str, str] = {
    "isuzu": "isuzu",
    "dodge-ram": "dodge",
    "dodge": "dodge",
}


def _category_url(slug: str) -> str:
    return reverse("catalog:category", kwargs={"category_slug": slug})


def _brand_url(slug: str) -> str:
    return reverse("catalog:brand", kwargs={"brand_slug": slug})


def _vehicle_url(slug: str) -> str:
    return reverse("catalog:vehicle_detail", kwargs={"slug": slug})


def _resolve_product_target(slug: str) -> str:
    mapped = LEGACY_PRODUCT_SLUGS.get(slug)
    if mapped:
        kind, value = mapped.split(":", 1)
        if kind == "vehicle":
            return _vehicle_url(value)
        return _category_url(value)

    from catalog.models import Vehicle

    candidates = [slug]
    stripped = re.sub(r"-(19|20)\d{2}(-god)?$", "", slug)
    if stripped and stripped != slug:
        candidates.append(stripped)
    stripped2 = re.sub(r"-god$", "", stripped or slug)
    if stripped2 and stripped2 not in candidates:
        candidates.append(stripped2)

    for candidate in candidates:
        if Vehicle.objects.filter(slug=candidate).exists():
            return _vehicle_url(candidate)

    return _category_url("cars")


def _resolve_brand_target(slug: str) -> str:
    from catalog.models import Brand

    mapped = LEGACY_BRAND_SLUGS.get(slug, slug)
    if Brand.objects.filter(slug=mapped).exists():
        return _brand_url(mapped)
    if Brand.objects.filter(slug=slug).exists():
        return _brand_url(slug)
    return _category_url("cars")


def legacy_product_redirect(request, slug: str):
    return HttpResponsePermanentRedirect(_resolve_product_target(slug))


def legacy_brand_redirect(request, slug: str):
    return HttpResponsePermanentRedirect(_resolve_brand_target(slug))


def legacy_wp_date_post_redirect(request, year: int, month: int, day: int, slug: str):
    return HttpResponsePermanentRedirect("/")


urlpatterns = [
    path(
        "o-kompanii/",
        RedirectView.as_view(url="/about/", permanent=True),
    ),
    path(
        "category/uncategorized/",
        RedirectView.as_view(url="/", permanent=True),
    ),
    path(
        "product-category/auto/",
        RedirectView.as_view(url="/catalog/category/cars/", permanent=True),
    ),
    path(
        "product-category/spec/",
        RedirectView.as_view(url="/catalog/category/special/", permanent=True),
    ),
    re_path(
        r"^product-category/spec/грузовые-автомобили/?$",
        RedirectView.as_view(url="/catalog/category/trucks/", permanent=True),
    ),
    re_path(
        r"^product-category/spec/автовышки/?$",
        RedirectView.as_view(
            url="/catalog/category/special_lifts/", permanent=True
        ),
    ),
    re_path(
        r"^легковые-автомобили-и-спецтехника-из/?$",
        RedirectView.as_view(url="/catalog/category/cars/", permanent=True),
    ),
    re_path(
        r"^product/(?P<slug>[^/]+)/?$",
        legacy_product_redirect,
    ),
    re_path(
        r"^бренд/(?P<slug>[^/]+)/?$",
        legacy_brand_redirect,
    ),
    re_path(
        r"^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<slug>[^/]+)/?$",
        legacy_wp_date_post_redirect,
    ),
]
