from utils.sitemaps import SiteUrlSitemap

from .models import Brand, Category, Vehicle


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
        return Brand.objects.filter(vehicles__is_published=True).distinct()


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
