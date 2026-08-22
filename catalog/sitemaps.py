from django.urls import reverse

from utils.sitemaps import SiteUrlSitemap

from .models import Brand, CarModel, Category, Vehicle
from .seo_pages import seo_brands_queryset, seo_model_pages_enabled


class VehicleSitemap(SiteUrlSitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Vehicle.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


class BrandSitemap(SiteUrlSitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        if seo_model_pages_enabled():
            return seo_brands_queryset()
        return Brand.objects.filter(vehicles__is_published=True).distinct()


class CarModelSitemap(SiteUrlSitemap):
    changefreq = "weekly"
    priority = 0.75

    def items(self):
        if not seo_model_pages_enabled():
            return []
        return CarModel.objects.filter(is_published=True).select_related("brand")

    def lastmod(self, obj):
        return obj.updated_at


class BrandsIndexSitemap(SiteUrlSitemap):
    changefreq = "weekly"
    priority = 0.65

    def items(self):
        return ["index"] if seo_model_pages_enabled() else []

    def location(self, item):
        return reverse("catalog:brands_index")


class CategorySitemap(SiteUrlSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        """Only categories that have published vehicles in their subtree (incl. self)."""
        vehicle_cat_ids = set(
            Vehicle.objects.filter(is_published=True).values_list(
                "category_id", flat=True
            )
        )
        vehicle_cat_ids.discard(None)
        if not vehicle_cat_ids:
            return Category.objects.none()

        parent_map = dict(Category.objects.values_list("pk", "parent_id"))
        expanded = set(vehicle_cat_ids)
        for cid in list(vehicle_cat_ids):
            pid = parent_map.get(cid)
            while pid:
                expanded.add(pid)
                pid = parent_map.get(pid)
        return Category.objects.filter(pk__in=expanded).order_by("name")
