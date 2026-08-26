from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Brand, Category, Vehicle


@override_settings(RATELIMIT_ENABLE=False)
class LegacyWordpressRedirectTests(TestCase):
    def setUp(self):
        self.cars, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые"}
        )
        self.trucks, _ = Category.objects.get_or_create(
            slug="trucks", defaults={"name": "Коммерческий"}
        )
        Category.objects.get_or_create(
            slug="special_lifts", defaults={"name": "Автовышки"}
        )
        Category.objects.get_or_create(
            slug="special", defaults={"name": "Спецтехника"}
        )
        self.brand, _ = Brand.objects.get_or_create(
            slug="honda", defaults={"name": "Honda"}
        )
        self.isuzu, _ = Brand.objects.get_or_create(
            slug="isuzu", defaults={"name": "Isuzu"}
        )
        Brand.objects.filter(slug="dodge").delete()
        self.vehicle, _ = Vehicle.objects.get_or_create(
            slug="honda-vezel",
            defaults={
                "title": "Honda Vezel",
                "brand": self.brand,
                "category": self.cars,
                "year": 2021,
                "is_published": True,
            },
        )
        audi, _ = Brand.objects.get_or_create(slug="audi", defaults={"name": "Audi"})
        self.audi, _ = Vehicle.objects.get_or_create(
            slug="audi-q3",
            defaults={
                "title": "Audi Q3",
                "brand": audi,
                "category": self.cars,
                "year": 2022,
                "is_published": True,
            },
        )

    def test_exact_legacy_pages(self):
        cases = [
            ("/o-kompanii/", "/about/"),
            ("/category/uncategorized/", "/"),
            ("/product-category/auto/", "/catalog/category/cars/"),
            ("/product-category/auto/?products-per-page=all", "/catalog/category/cars/"),
            ("/product-category/spec/", "/catalog/category/special/"),
            ("/product-category/spec/грузовые-автомобили/", "/catalog/category/trucks/"),
            ("/product-category/spec/автовышки/", "/catalog/category/special_lifts/"),
            (
                "/легковые-автомобили-и-спецтехника-из/",
                "/catalog/category/cars/",
            ),
            ("/2024/01/06/hello-world/", "/"),
        ]
        for source, target in cases:
            with self.subTest(source=source):
                response = self.client.get(source)
                self.assertEqual(response.status_code, 301, msg=source)
                self.assertEqual(response.url, target)

    def test_legacy_product_to_vehicle(self):
        response = self.client.get("/product/honda-vezel-2021/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("catalog:vehicle_detail", kwargs={"slug": "honda-vezel"}),
        )

        response = self.client.get("/product/audi-q3/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("catalog:vehicle_detail", kwargs={"slug": "audi-q3"}),
        )

    def test_legacy_product_fallback_category(self):
        response = self.client.get("/product/автовышка-isuzu-giga-45m/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse(
                "catalog:category", kwargs={"category_slug": "special_lifts"}
            ),
        )

        response = self.client.get("/product/грузовой-фургон-dodge-ram/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("catalog:category", kwargs={"category_slug": "trucks"}),
        )

    def test_legacy_brand(self):
        response = self.client.get("/бренд/isuzu/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("catalog:brand", kwargs={"brand_slug": "isuzu"}),
        )

        response = self.client.get("/бренд/dodge-ram/")
        self.assertEqual(response.status_code, 301)
        # No dodge brand in fixtures → cars fallback.
        self.assertEqual(
            response.url,
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
        )
