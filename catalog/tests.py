from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .cache_helpers import invalidate_nav_cache
from .models import Brand, CarModel, Category, Vehicle, VehicleImage


class RemovedDealerOfferTests(TestCase):
    def test_old_offer_urls_are_gone(self):
        self.assertEqual(
            self.client.get("/catalog/dealer/report/create/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/catalog/report/TG-X/key/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/catalog/report/TG-X/key/download_photos/").status_code,
            404,
        )


class VehicleDossierTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="TestBrand", slug="testbrand")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        self.vehicle = Vehicle.objects.create(
            title="No Report Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=0,
            is_published=True,
            slug="no-report-car",
        )

    def test_dossier_404_without_report(self):
        response = self.client.get(
            reverse("catalog:vehicle_dossier", kwargs={"slug": self.vehicle.slug})
        )
        self.assertEqual(response.status_code, 404)


@override_settings(RATELIMIT_ENABLE=False)
class CatalogPagesTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="CatalogBrand", slug="catalogbrand")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        self.vehicle = Vehicle.objects.create(
            title="Published Car",
            brand=self.brand,
            category=self.category,
            year=2023,
            mileage=1000,
            price_rub=2500000,
            is_published=True,
            show_on_home=False,
            slug="published-car",
        )
        Vehicle.objects.create(
            title="Hidden Car",
            brand=self.brand,
            category=self.category,
            year=2022,
            mileage=5000,
            is_published=False,
            slug="hidden-car",
        )

    def test_home_ok(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        cache_control = response.get("Cache-Control", "")
        self.assertIn("max-age=30", cache_control)
        self.assertIn("private", cache_control)
        self.assertNotIn("no-store", cache_control)
        html = response.content.decode("utf-8")
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)
        self.assertIn("fonts/manrope-cyrillic-wght.woff2", html)
        self.assertIn("Автомобили под заказ из Китая", html)
        self.assertIn("Автомобили под заказ из Китая | Техника Года", html)

    def test_home_repeat_visit_uses_cache(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from .cache_helpers import invalidate_home_sections_cache

        invalidate_nav_cache()
        invalidate_home_sections_cache()
        self.client.get(reverse("home"))
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx), 8)

    def test_home_picker_has_three_niches(self):
        trucks, _ = Category.objects.get_or_create(
            slug="trucks", defaults={"name": "Коммерческий транспорт"}
        )
        special, _ = Category.objects.get_or_create(
            slug="special", defaults={"name": "Спецтехника"}
        )
        Category.objects.get_or_create(
            slug="trucks_trucks", defaults={"name": "Грузовики", "parent": trucks}
        )
        Category.objects.get_or_create(
            slug="special_lifts", defaults={"name": "Автовышки", "parent": special}
        )
        Category.objects.get_or_create(
            slug="special_cranes",
            defaults={"name": "Башенные краны", "parent": special},
        )
        invalidate_nav_cache()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Подобрать авто")
        self.assertContains(response, "Подобрать коммерческий транспорт")
        self.assertContains(response, "Подобрать спецтехнику")
        self.assertContains(response, "Тип транспорта")
        self.assertContains(response, "Тип техники")
        self.assertContains(response, "Грузовики")
        self.assertContains(response, "Автовышки")
        self.assertContains(response, "Башенные краны")
        self.assertContains(response, 'value="cars"')
        self.assertContains(response, 'value="trucks"')
        self.assertContains(response, 'value="special"')
        self.assertContains(response, 'value="trucks_trucks"')
        self.assertContains(response, 'value="special_lifts"')
        self.assertContains(response, 'value="special_cranes"')
        self.assertNotContains(response, "Фронтальные погрузчики")
        self.assertNotContains(response, "Вилочные погрузчики")
        self.assertNotContains(response, "Экскаваторы-погрузчики")
        self.assertContains(
            response, reverse("catalog:category", kwargs={"category_slug": "trucks"})
        )
        self.assertContains(
            response, reverse("catalog:category", kwargs={"category_slug": "special"})
        )

    def test_home_shows_only_flagged_published_cars(self):
        from .cache_helpers import invalidate_home_sections_cache

        off_home = Vehicle.objects.create(
            title="Catalog Only Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=200,
            price_rub=1800000,
            is_published=True,
            show_on_home=False,
            slug="catalog-only-car",
        )
        on_home = Vehicle.objects.create(
            title="Home Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=300,
            price_rub=1900000,
            is_published=True,
            show_on_home=True,
            slug="home-car",
        )
        unpublished_home = Vehicle.objects.create(
            title="Draft Home Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=400,
            price_rub=2000000,
            is_published=False,
            show_on_home=True,
            slug="draft-home-car",
        )
        invalidate_home_sections_cache()
        home = self.client.get(reverse("home"))
        self.assertContains(home, on_home.title)
        self.assertNotContains(home, off_home.title)
        self.assertNotContains(home, unpublished_home.title)
        self.assertNotContains(home, "Published Car")

        catalog = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"})
        )
        self.assertContains(catalog, on_home.title)
        self.assertContains(catalog, off_home.title)
        self.assertContains(catalog, "Published Car")
        self.assertNotContains(catalog, unpublished_home.title)

    def test_list_shows_published_only(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Car")
        self.assertNotContains(response, "Hidden Car")
        self.assertContains(response, "по курсу 12.48")
        self.assertContains(response, "1 000 км")
        self.assertNotContains(response, ">1000 км")

    def test_body_type_filter_matches_child_category_and_singular_body_type(self):
        sedan, _ = Category.objects.get_or_create(
            slug="cars_sedan", defaults={"name": "Седаны", "parent": self.category}
        )
        if sedan.parent_id != self.category.id:
            sedan.parent = self.category
            sedan.save(update_fields=["parent"])
        minivan, _ = Category.objects.get_or_create(
            slug="cars_minivan", defaults={"name": "Минивэны", "parent": self.category}
        )
        if minivan.parent_id != self.category.id:
            minivan.parent = self.category
            minivan.save(update_fields=["parent"])

        sedan_vehicle = Vehicle.objects.create(
            title="Sedan Car",
            brand=self.brand,
            category=sedan,
            year=2023,
            mileage=1100,
            price_rub=2700000,
            is_published=True,
            slug="sedan-car",
        )
        minivan_vehicle = Vehicle.objects.create(
            title="Minivan Car",
            brand=self.brand,
            category=self.category,
            body_type="Минивэн",
            year=2023,
            mileage=1200,
            price_rub=2800000,
            is_published=True,
            slug="minivan-car",
        )
        other_vehicle = Vehicle.objects.create(
            title="SUV Car",
            brand=self.brand,
            category=self.category,
            body_type="Внедорожник",
            year=2023,
            mileage=1300,
            price_rub=2900000,
            is_published=True,
            slug="suv-car",
        )

        sedan_response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"body_type": "cars_sedan"},
        )
        self.assertContains(sedan_response, sedan_vehicle.title)
        self.assertNotContains(sedan_response, minivan_vehicle.title)
        self.assertNotContains(sedan_response, other_vehicle.title)

        minivan_response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"body_type": "cars_minivan"},
        )
        self.assertContains(minivan_response, minivan_vehicle.title)
        self.assertNotContains(minivan_response, sedan_vehicle.title)
        self.assertNotContains(minivan_response, other_vehicle.title)

    def test_engine_type_filter(self):
        electric = Vehicle.objects.create(
            title="Electric Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=100,
            price_rub=3500000,
            engine_type="electric",
            is_published=True,
            slug="electric-car",
        )
        hybrid = Vehicle.objects.create(
            title="Hybrid Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=200,
            price_rub=3200000,
            engine_type="hybrid",
            is_published=True,
            slug="hybrid-car",
        )
        petrol = Vehicle.objects.create(
            title="Petrol Car",
            brand=self.brand,
            category=self.category,
            year=2023,
            mileage=300,
            price_rub=2100000,
            engine_type="petrol",
            is_published=True,
            slug="petrol-car",
        )

        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"engine_type": "electric"},
        )
        self.assertContains(response, electric.title)
        self.assertNotContains(response, hybrid.title)
        self.assertNotContains(response, petrol.title)

        hybrid_response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"engine_type": "hybrid"},
        )
        self.assertContains(hybrid_response, hybrid.title)
        self.assertNotContains(hybrid_response, electric.title)

    def test_engine_type_syncs_from_specs_on_save(self):
        vehicle = Vehicle.objects.create(
            title="Fuel Sync Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=0,
            price_rub=4000000,
            specs={"fuelType": "Plug-in Hybrid"},
            is_published=True,
            slug="fuel-sync-car",
        )
        self.assertEqual(vehicle.engine_type, "hybrid")

    def test_list_redirects_to_default_category(self):
        response = self.client.get(reverse("catalog:index"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("catalog:category", kwargs={"category_slug": "cars"})
        )

    def test_unknown_category_path_is_404(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "does-not-exist"})
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_get_category_hides_results(self):
        response = self.client.get(
            reverse("catalog:index"),
            {"category": "does-not-exist", "q": "Published"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Published Car")

    def test_trucks_listing_shows_commercial_chips(self):
        trucks, _ = Category.objects.get_or_create(
            slug="trucks", defaults={"name": "Коммерческий транспорт"}
        )
        Category.objects.get_or_create(
            slug="trucks_trucks", defaults={"name": "Грузовики", "parent": trucks}
        )
        invalidate_nav_cache()
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "trucks"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Весь коммерческий")
        self.assertContains(response, "Грузовики")
        self.assertContains(
            response, 'class="catalog-brand-chip is-active">Весь коммерческий'
        )
        self.assertNotContains(
            response, 'class="catalog-brand-chip is-active">Все легковые'
        )

    def test_legacy_query_category_redirects_to_clean_url(self):
        response = self.client.get(
            reverse("catalog:index"), {"category": "cars_sedan"}
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("catalog:category", kwargs={"category_slug": "cars_sedan"}),
        )

    def test_detail_ok(self):
        response = self.client.get(
            reverse("catalog:vehicle_detail", kwargs={"slug": self.vehicle.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Car")
        self.assertContains(response, "<h1")
        self.assertContains(response, '"Car"')
        self.assertContains(response, "1 000 км")
        self.assertNotContains(response, ">1000 км")
        self.assertContains(response, "mileageFromOdometer")
        self.assertContains(response, 'id="vehicle-lightbox"')
        self.assertContains(response, "js/detail.js")
        self.assertContains(response, 'aria-label="Хлебные крошки"')
        self.assertContains(
            response,
            "Цена под ключ до Благовещенска по курсу 12.48. "
            "Актуальную цену на день заявки уточняйте у менеджера.",
        )
        self.assertNotContains(response, "Цена в карточке ориентировочная")

    def test_detail_hides_duplicate_english_spec_cards(self):
        cars, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые автомобили"}
        )
        sedan, _ = Category.objects.get_or_create(
            slug="cars_sedan",
            defaults={"name": "Седаны", "parent": cars},
        )
        if sedan.parent_id != cars.id:
            sedan.parent = cars
            sedan.save(update_fields=["parent"])
        self.vehicle.category = sedan
        self.vehicle.color = "Белый"
        self.vehicle.transmission = "Робот"
        self.vehicle.body_type = "Минивэн"
        self.vehicle.horsepower = 159
        self.vehicle.engine_type = "petrol"
        self.vehicle.specs = {
            "color": "Белый",
            "gearbox": "Робот",
            "transmission": "Робот",
            "bodyType": "Минивэн",
            "fuelType": "Бензин",
            "engine_vol": "1.5",
        }
        self.vehicle.save()
        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertContains(response, "Цвет")
        self.assertContains(response, "Коробка передач")
        self.assertContains(response, "Тип двигателя")
        self.assertContains(response, "Бензин")
        self.assertContains(response, "Объём двигателя")
        self.assertNotContains(response, ">color<")
        self.assertNotContains(response, ">gearbox<")
        self.assertNotContains(response, ">transmission<")
        self.assertNotContains(response, ">bodyType<")
        self.assertNotContains(response, ">fuelType<")

    def test_detail_uses_vehicle_cny_rate(self):
        self.vehicle.cny_rate = "13.10"
        self.vehicle.save(update_fields=["cny_rate"])
        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertContains(response, "по курсу 13.10")

    def test_detail_renders_pasted_spec_sheet(self):
        self.vehicle.description = (
            "[Название автомобиля] Volkswagen Bora (099526)\n"
            "【Цвет】 серый\n"
            "[Пробег] 30 000 километров"
        )
        self.vehicle.save(update_fields=["description"])
        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertContains(response, "vehicle-spec-sheet")
        self.assertContains(response, "Название автомобиля")
        self.assertContains(response, "Volkswagen Bora (099526)")
        self.assertContains(response, "30 000 километров")
        self.assertNotContains(response, "Топ-опции")

    def test_detail_merges_empty_spec_label(self):
        self.vehicle.description = (
            "[Цвет] серый\n"
            "【Дополнительно】\n"
            "[Пробег] 30 000 километров"
        )
        self.vehicle.save(update_fields=["description"])
        response = self.client.get(self.vehicle.get_absolute_url())
        self.assertContains(response, "vehicle-spec-sheet__heading")
        self.assertContains(response, "Дополнительно")
        self.assertNotContains(response, "vehicle-spec-sheet__value\">—")

    def test_category_has_h1_and_indexable(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Автомобили под заказ из Китая")
        self.assertContains(response, "<h1")
        self.assertIn("max-age=30", response.get("Cache-Control", ""))
        self.assertIn("private", response.get("Cache-Control", ""))
        self.assertContains(response, 'content="index, follow"')
        self.assertNotContains(response, 'content="noindex, follow"')

    def test_filtered_listing_is_noindex(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"price_from": "1000000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow"')

    def test_pagination_is_noindex(self):
        for i in range(12):
            Vehicle.objects.create(
                title=f"Page Car {i}",
                brand=self.brand,
                category=self.category,
                year=2020,
                mileage=1000 + i,
                is_published=True,
                slug=f"page-car-{i}",
            )
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"}),
            {"page": "2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow"')

    def test_search_ajax_rate_limit_disabled(self):
        response = self.client.get(
            reverse("catalog:search_ajax"),
            {"q": "Published"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 1)
        self.assertIn("Published", data[0]["title"])
        self.assertNotIn("&amp;", data[0]["title"])


class VehicleColorAndCacheTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="ColorBrand", slug="colorbrand")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )

    def test_save_syncs_color_from_specs(self):
        vehicle = Vehicle.objects.create(
            title="Color Sync Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=0,
            is_published=True,
            slug="color-sync-car",
            specs={"color": "Белый"},
        )
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.color, "Белый")

    def test_available_colors_uses_field_not_full_scan(self):
        from django.core.cache import cache

        from .cache_helpers import COLORS_CACHE_KEY, available_colors

        cache.delete(COLORS_CACHE_KEY)
        Vehicle.objects.create(
            title="Red Car",
            brand=self.brand,
            category=self.category,
            year=2023,
            is_published=True,
            slug="red-car",
            color="Красный",
        )
        Vehicle.objects.create(
            title="Draft Car",
            brand=self.brand,
            category=self.category,
            year=2022,
            is_published=False,
            slug="draft-car",
            color="Синий",
        )
        colors = available_colors()
        self.assertIn("Красный", colors)
        self.assertNotIn("Синий", colors)
        # Second call hits cache
        self.assertEqual(available_colors(), colors)


@override_settings(RATELIMIT_ENABLE=False)
class VehicleFilterAndBadgeTests(TestCase):
    def setUp(self):
        self.cars, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые"}
        )
        self.bought_cat, _ = Category.objects.get_or_create(
            slug="cars_bought",
            defaults={"name": "Выкупленные", "parent": self.cars},
        )
        if self.bought_cat.parent_id != self.cars.id:
            self.bought_cat.parent = self.cars
            self.bought_cat.save(update_fields=["parent"])
        self.cars_new, _ = Category.objects.get_or_create(
            slug="cars_new",
            defaults={"name": "Новые", "parent": self.cars},
        )
        if self.cars_new.parent_id != self.cars.id:
            self.cars_new.parent = self.cars
            self.cars_new.save(update_fields=["parent"])
        self.brand = Brand.objects.create(name="FilterBrand", slug="filterbrand")
        self.new_car = Vehicle.objects.create(
            title="New Zero",
            brand=self.brand,
            category=self.cars_new,
            year=2025,
            mileage=0,
            is_published=True,
            is_featured=False,
            slug="new-zero",
            price_rub=1000000,
        )
        self.bought_flag = Vehicle.objects.create(
            title="Bought Flag",
            brand=self.brand,
            category=self.cars,
            year=2022,
            mileage=40000,
            is_published=True,
            is_featured=True,
            slug="bought-flag",
            price_rub=2000000,
        )
        self.bought_cat_car = Vehicle.objects.create(
            title="Bought Cat",
            brand=self.brand,
            category=self.bought_cat,
            year=2021,
            mileage=10000,
            is_published=True,
            is_featured=False,
            slug="bought-cat",
            price_rub=1500000,
        )
        self.used = Vehicle.objects.create(
            title="Used Plain",
            brand=self.brand,
            category=self.cars,
            year=2020,
            mileage=80000,
            is_published=True,
            is_featured=False,
            slug="used-plain",
            price_rub=900000,
        )

    def test_cars_new_is_category_only_not_mileage(self):
        Vehicle.objects.create(
            title="Tech Mileage New",
            brand=self.brand,
            category=self.cars_new,
            year=2025,
            mileage=2500,
            is_published=True,
            is_featured=False,
            slug="tech-mileage-new",
            price_rub=2_800_000,
        )
        # Same mileage under plain cars must not appear in «Новые».
        Vehicle.objects.create(
            title="Low Miles But Not New Cat",
            brand=self.brand,
            category=self.cars,
            year=2024,
            mileage=100,
            is_published=True,
            is_featured=False,
            slug="low-miles-plain",
            price_rub=1_200_000,
        )
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_new"})
        )
        self.assertEqual(response.status_code, 200)
        titles = [v.title for v in response.context["vehicles"]]
        self.assertIn("New Zero", titles)
        self.assertIn("Tech Mileage New", titles)
        self.assertNotIn("Used Plain", titles)
        self.assertNotIn("Low Miles But Not New Cat", titles)

    def test_cars_bought_filter(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_bought"})
        )
        self.assertEqual(response.status_code, 200)
        titles = [v.title for v in response.context["vehicles"]]
        self.assertIn("Bought Flag", titles)
        self.assertIn("Bought Cat", titles)
        self.assertNotIn("Used Plain", titles)
        self.assertNotIn("New Zero", titles)

    def test_featured_and_new_in_both_filters(self):
        Vehicle.objects.create(
            title="New Featured",
            brand=self.brand,
            category=self.cars_new,
            year=2025,
            mileage=1200,
            is_published=True,
            is_new=True,
            is_featured=True,
            slug="new-featured",
            price_rub=3000000,
        )
        new_response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_new"})
        )
        new_titles = [v.title for v in new_response.context["vehicles"]]
        self.assertIn("New Featured", new_titles)

        bought_response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_bought"})
        )
        bought_titles = [v.title for v in bought_response.context["vehicles"]]
        self.assertIn("New Featured", bought_titles)

    def test_featured_truck_not_in_cars_bought(self):
        trucks, _ = Category.objects.get_or_create(
            slug="trucks", defaults={"name": "Грузовики"}
        )
        Vehicle.objects.create(
            title="Featured Truck",
            brand=self.brand,
            category=trucks,
            year=2022,
            mileage=50000,
            is_published=True,
            is_featured=True,
            slug="featured-truck",
            price_rub=4000000,
        )
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_bought"})
        )
        titles = [v.title for v in response.context["vehicles"]]
        self.assertNotIn("Featured Truck", titles)
        self.assertIn("Bought Flag", titles)

    def test_bought_car_appears_in_matching_body_type_category(self):
        crossover, _ = Category.objects.get_or_create(
            slug="cars_crossover",
            defaults={"name": "Кроссоверы", "parent": self.cars},
        )
        if crossover.parent_id != self.cars.id:
            crossover.parent = self.cars
            crossover.save(update_fields=["parent"])
        sedan, _ = Category.objects.get_or_create(
            slug="cars_sedan",
            defaults={"name": "Седаны", "parent": self.cars},
        )
        if sedan.parent_id != self.cars.id:
            sedan.parent = self.cars
            sedan.save(update_fields=["parent"])

        bought_crossover = Vehicle.objects.create(
            title="Bought Crossover",
            brand=self.brand,
            category=self.bought_cat,
            body_type="Кроссовер",
            year=2023,
            mileage=12000,
            is_published=True,
            is_featured=False,
            slug="bought-crossover",
            price_rub=2_500_000,
        )
        featured_sedan = Vehicle.objects.create(
            title="Featured Sedan",
            brand=self.brand,
            category=sedan,
            body_type="Седан",
            year=2022,
            mileage=30000,
            is_published=True,
            is_featured=True,
            slug="featured-sedan",
            price_rub=1_800_000,
        )

        crossover_resp = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_crossover"})
        )
        crossover_titles = [v.title for v in crossover_resp.context["vehicles"]]
        self.assertIn(bought_crossover.title, crossover_titles)
        self.assertNotIn(featured_sedan.title, crossover_titles)
        self.assertNotIn("Bought Cat", crossover_titles)

        sedan_resp = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_sedan"})
        )
        sedan_titles = [v.title for v in sedan_resp.context["vehicles"]]
        self.assertIn(featured_sedan.title, sedan_titles)
        self.assertNotIn(bought_crossover.title, sedan_titles)

        bought_resp = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_bought"})
        )
        bought_titles = [v.title for v in bought_resp.context["vehicles"]]
        self.assertIn(bought_crossover.title, bought_titles)
        self.assertIn(featured_sedan.title, bought_titles)

    def test_mileage_display_groups_thousands(self):
        from catalog.templatetags.catalog_extras import mileage_display

        self.assertEqual(mileage_display(30000), "30 000 км")
        self.assertEqual(mileage_display(0), "0 км")
        self.assertEqual(mileage_display(None), "уточняется")
        self.assertEqual(mileage_display("abc"), "уточняется")

    def test_badge_items_new_and_bought(self):
        from catalog.templatetags.catalog_extras import vehicle_badge_items

        new_badges = vehicle_badge_items(self.new_car)
        self.assertEqual([b["text"] for b in new_badges], ["Новые"])

        new_with_mileage = Vehicle.objects.create(
            title="New With Miles",
            brand=self.brand,
            category=self.cars_new,
            year=2026,
            mileage=1656,
            is_published=True,
            is_new=True,
            slug="new-with-miles",
        )
        self.assertEqual(
            [b["text"] for b in vehicle_badge_items(new_with_mileage)], ["Новые"]
        )

        flag_only = Vehicle.objects.create(
            title="New By Flag",
            brand=self.brand,
            category=self.cars,
            year=2026,
            mileage=2000,
            is_published=True,
            is_new=True,
            slug="new-by-flag",
        )
        self.assertEqual([b["text"] for b in vehicle_badge_items(flag_only)], ["Новые"])
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_new"})
        )
        self.assertIn("New By Flag", [v.title for v in response.context["vehicles"]])

        bought_badges = vehicle_badge_items(self.bought_flag)
        self.assertEqual([b["text"] for b in bought_badges], ["Выкупленные"])

        both = Vehicle.objects.create(
            title="Both",
            brand=self.brand,
            category=self.cars,
            year=2024,
            mileage=2000,
            is_published=True,
            is_new=True,
            is_featured=True,
            slug="both-badges",
        )
        texts = [b["text"] for b in vehicle_badge_items(both)]
        self.assertEqual(texts, ["Новые", "Выкупленные"])

        cat_only = vehicle_badge_items(self.bought_cat_car)
        self.assertEqual([b["text"] for b in cat_only], ["Выкупленные"])


class VehiclePublishDefaultTests(TestCase):
    def test_new_vehicle_is_unpublished(self):
        brand = Brand.objects.create(name="DraftBrand", slug="draftbrand")
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        vehicle = Vehicle.objects.create(
            title="Draft Car",
            brand=brand,
            category=category,
            year=2024,
            price_rub=1000000,
        )
        self.assertFalse(vehicle.is_published)
        self.assertTrue(vehicle.show_on_home)

    def test_home_shows_newest_even_without_featured_flag(self):
        from .cache_helpers import HOME_SECTION_LIMIT, invalidate_home_sections_cache

        brand = Brand.objects.create(name="HomeOrderBrand", slug="homeorderbrand")
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        for i in range(HOME_SECTION_LIMIT):
            Vehicle.objects.create(
                title=f"Featured Slot {i}",
                brand=brand,
                category=category,
                year=2023,
                mileage=1000 + i,
                price_rub=2_000_000 + i,
                is_published=True,
                show_on_home=True,
                is_featured=True,
                slug=f"featured-slot-{i}",
            )
        newest = Vehicle.objects.create(
            title="Fresh New Car",
            brand=brand,
            category=category,
            year=2025,
            mileage=0,
            price_rub=3_500_000,
            is_published=True,
            show_on_home=True,
            is_featured=False,
            slug="fresh-new-car",
        )
        invalidate_home_sections_cache()
        home = self.client.get(reverse("home"))
        self.assertContains(home, newest.title)
        self.assertNotContains(home, "Featured Slot 0")


@override_settings(RATELIMIT_ENABLE=False)
class VehicleImageVariantTests(TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        media = override_settings(MEDIA_ROOT=self.tmp.name)
        media.enable()
        self.addCleanup(media.disable)
        self.brand = Brand.objects.create(name="ImgBrand", slug="imgbrand")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )

    def test_saved_jpeg_gets_webp_master_and_card_srcset(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from utils.image_processing import variant_storage_name

        buf = BytesIO()
        Image.new("RGB", (1800, 1000), (40, 40, 40)).save(buf, format="JPEG")
        buf.seek(0)
        upload = SimpleUploadedFile("cover.jpg", buf.read(), content_type="image/jpeg")
        vehicle = Vehicle(
            title="Photo Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=100,
            price_rub=2000000,
            is_published=True,
            show_on_home=True,
            slug="photo-car",
        )
        vehicle.main_image = upload
        vehicle.save()
        self.assertTrue(vehicle.main_image.name.lower().endswith(".webp"))
        self.assertTrue(
            vehicle.main_image.storage.exists(
                variant_storage_name(vehicle.main_image.name, 800)
            )
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "srcset=")
        self.assertContains(response, ".w800.webp")

    def test_cover_is_included_in_detail_gallery(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from catalog.templatetags.catalog_extras import vehicle_gallery_images

        def _jpeg(name):
            buf = BytesIO()
            Image.new("RGB", (800, 600), (10, 10, 10)).save(buf, format="JPEG")
            buf.seek(0)
            return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")

        vehicle = Vehicle.objects.create(
            title="Cover Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=100,
            price_rub=1500000,
            is_published=True,
            slug="cover-car",
        )
        vehicle.main_image = _jpeg("cover.jpg")
        vehicle.save()
        VehicleImage.objects.create(vehicle=vehicle, image=_jpeg("gallery.jpg"), order=1)
        vehicle.refresh_from_db()
        slides = vehicle_gallery_images(vehicle)
        self.assertGreaterEqual(len(slides), 2)
        self.assertEqual(slides[0].name, vehicle.main_image.name)
        response = self.client.get(vehicle.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, vehicle.main_image.url)


@override_settings(RATELIMIT_ENABLE=False)
class AdminBulkCacheTests(TestCase):
    def test_unpublish_selected_invalidates_home_cache(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.core.cache import cache
        from django.test import RequestFactory

        from catalog.admin import VehicleAdmin
        from catalog.cache_helpers import (
            HOME_SECTION_LIMIT,
            HOME_SECTIONS_CACHE_KEY,
            home_sections,
        )

        brand = Brand.objects.create(name="CacheBrand", slug="cachebrand")
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        vehicle = Vehicle.objects.create(
            title="Cached Car",
            brand=brand,
            category=category,
            year=2024,
            is_published=True,
            slug="cached-car",
        )
        home_sections()
        cache_key = f"{HOME_SECTIONS_CACHE_KEY}:{HOME_SECTION_LIMIT}"
        self.assertIsNotNone(cache.get(cache_key))

        request = RequestFactory().post("/")
        request.session = {}
        request._messages = FallbackStorage(request)
        VehicleAdmin(Vehicle, AdminSite()).unpublish_selected(
            request, Vehicle.objects.filter(pk=vehicle.pk)
        )
        self.assertIsNone(cache.get(cache_key))
        self.assertFalse(Vehicle.objects.get(pk=vehicle.pk).is_published)


class VehicleAdminAddFormTests(TestCase):
    def test_ckeditor_upload_url_is_wired(self):
        """Admin vehicle form uses CKEditor5Widget; upload reverse must exist."""
        from django.urls import reverse

        self.assertEqual(
            reverse("ck_editor_5_upload_file"),
            "/ckeditor5/image_upload/",
        )

    def test_add_form_renders_without_reverse_error(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from catalog.admin import VehicleAdmin

        user = get_user_model().objects.create_superuser(
            "vehicle-admin", "va@example.com", "pass-not-used"
        )
        request = RequestFactory().get("/admin/catalog/vehicle/add/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = VehicleAdmin(Vehicle, AdminSite()).add_view(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tg-spec-paste")
        self.assertContains(response, "[Название автомобиля]")


class VehicleAdminGalleryGridTests(TestCase):
    def test_change_form_renders_horizontal_photo_grid(self):
        import tempfile
        from io import BytesIO

        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory, override_settings
        from PIL import Image

        from catalog.admin import VehicleAdmin

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        media = override_settings(MEDIA_ROOT=tmp.name)
        media.enable()
        self.addCleanup(media.disable)

        brand = Brand.objects.create(name="GridBrand", slug="gridbrand")
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        vehicle = Vehicle.objects.create(
            title="Grid Car",
            brand=brand,
            category=category,
            year=2024,
            slug="grid-car",
        )
        buf = BytesIO()
        Image.new("RGB", (400, 300), (20, 20, 20)).save(buf, format="JPEG")
        buf.seek(0)
        VehicleImage.objects.create(
            vehicle=vehicle,
            image=SimpleUploadedFile("g.jpg", buf.read(), content_type="image/jpeg"),
            order=1,
        )

        user = get_user_model().objects.create_superuser(
            "gallery-admin", "ga@example.com", "pass-not-used"
        )
        request = RequestFactory().get(f"/admin/catalog/vehicle/{vehicle.pk}/change/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = VehicleAdmin(Vehicle, AdminSite()).change_view(
            request, str(vehicle.pk)
        )
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="gallery-group"')
        self.assertContains(response, "tg-photo-inline")
        self.assertContains(response, "tg-photo-grid")
        self.assertContains(response, "tg-photo-card__preview")
        self.assertContains(response, 'width="160"')
        self.assertContains(response, "vehicleimage_inline_sort.js")


class SpecSheetParseTests(TestCase):
    SAMPLE = (
        "[Название автомобиля] Volkswagen Bora (099526)\n"
        "[Модель] Версия 2023 200TSI DSG Smart Travel PRO\n"
        "【Режим привода】 2WD\n"
        "【Цвет】 серый\n"
        "【Дата производства】 Август 2022\n"
        "[Пробег] 30 000 километров\n"
        "【Объем двигателя】 1,2т\n"
        "【Мощность двигателя】85 кВт/116 л.с.\n"
        "【Коробка Передач】Робот DSG\n"
        "【Ключ】 2шт\n"
        "【Состояние автомобиля】 Оригинальная краска\n"
        "[Комплектация автомобиля] Smart Travel PRO"
    )

    def test_parses_mixed_brackets(self):
        from catalog.spec_sheet import parse_spec_sheet

        sheet = parse_spec_sheet(self.SAMPLE)
        self.assertTrue(sheet.has_rows)
        as_dict = dict(sheet.rows)
        self.assertEqual(as_dict["Название автомобиля"], "Volkswagen Bora (099526)")
        self.assertEqual(as_dict["Цвет"], "серый")
        self.assertEqual(as_dict["Мощность двигателя"], "85 кВт/116 л.с.")
        self.assertEqual(len(sheet.rows), 12)

    def test_parses_html_paragraphs(self):
        from catalog.spec_sheet import parse_spec_sheet

        html = "<p>[Модель] 200TSI</p><p>【Цвет】 серый</p>"
        sheet = parse_spec_sheet(html)
        self.assertEqual(sheet.rows, [("Модель", "200TSI"), ("Цвет", "серый")])

    def test_plain_text_without_labels_is_not_a_sheet(self):
        from catalog.spec_sheet import parse_spec_sheet

        sheet = parse_spec_sheet("Топ-опции:\n- Электролюк | Камера")
        self.assertFalse(sheet.has_rows)

    def test_empty_value_stays_empty_for_section_heading(self):
        from catalog.spec_sheet import parse_spec_sheet

        sheet = parse_spec_sheet("[Цвет] серый\n【Дополнительно】\n[Ключ] 2шт")
        self.assertEqual(
            sheet.rows,
            [("Цвет", "серый"), ("Дополнительно", ""), ("Ключ", "2шт")],
        )


class ListingIngestTests(TestCase):
    SAMPLE = (
        "[Название автомобиля] Volkswagen Bora (099526)\n"
        "[Модель] Версия 2023 200TSI DSG Smart Travel PRO\n"
        "【Цвет】 серый\n"
        "【Дата производства】 Август 2022\n"
        "[Пробег] 30 000 километров\n"
        "【Мощность двигателя】85 кВт/116 л.с.\n"
        "【Коробка Передач】Робот DSG\n"
        "【Тип кузова】 Седан\n"
        "[Комплектация автомобиля] Smart Travel PRO"
    )

    def test_parse_listing_maps_admin_fields(self):
        from catalog.listing_ingest import parse_listing_text

        data = parse_listing_text(self.SAMPLE)
        self.assertEqual(data.title, "Volkswagen Bora (099526)")
        self.assertEqual(data.brand_name, "Volkswagen")
        self.assertEqual(data.year, 2022)
        self.assertEqual(data.mileage, 30000)
        self.assertEqual(data.horsepower, 116)
        self.assertEqual(data.color, "Серый")
        self.assertEqual(data.transmission, "Робот DSG")
        self.assertEqual(data.body_type, "Седан")
        self.assertEqual(data.engine_type, "")
        self.assertEqual(data.specs, {})

    def test_parse_listing_detects_engine_type(self):
        from catalog.listing_ingest import parse_listing_text

        data = parse_listing_text(
            "[Название автомобиля] Zeekr 001\n"
            "【Тип топлива】 электрический\n"
            "[Пробег] 0 километров"
        )
        self.assertEqual(data.engine_type, "electric")

    def test_ingest_creates_brand_and_reuses_category(self):
        from catalog.listing_ingest import ingest_listing

        Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые автомобили"}
        )
        sedan, _ = Category.objects.get_or_create(
            slug="cars_sedan",
            defaults={"name": "Седаны"},
        )
        result = ingest_listing(self.SAMPLE)
        self.assertFalse(result.category_created)
        self.assertEqual(result.vehicle.brand.name, "Volkswagen")
        self.assertEqual(result.vehicle.category_id, sedan.id)
        self.assertEqual(result.vehicle.mileage, 30000)
        self.assertEqual(result.vehicle.year, 2022)
        self.assertFalse(result.vehicle.is_published)

        second = ingest_listing(self.SAMPLE)
        self.assertFalse(second.brand_created)
        self.assertEqual(Brand.objects.filter(name__iexact="Volkswagen").count(), 1)

    def test_ingest_creates_missing_category_under_cars(self):
        from catalog.listing_ingest import ingest_listing

        Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые автомобили"}
        )
        text = (
            "[Название автомобиля] Zeekr 001\n"
            "【Марка】 Zeekr\n"
            "【Категория】 Пикапы\n"
            "[Пробег] 0 километров"
        )
        result = ingest_listing(text)
        self.assertTrue(result.category_created)
        self.assertEqual(result.vehicle.category.name, "Пикапы")
        self.assertEqual(result.vehicle.category.parent.slug, "cars")
        self.assertEqual(result.vehicle.brand.name, "Zeekr")

        again = ingest_listing(text)
        self.assertFalse(again.category_created)
        self.assertEqual(result.vehicle.category_id, again.vehicle.category_id)

    def test_ingest_bought_uses_body_type_and_featured_flag(self):
        from catalog.listing_ingest import ingest_listing

        cars, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые автомобили"}
        )
        crossover, _ = Category.objects.get_or_create(
            slug="cars_crossover",
            defaults={"name": "Кроссоверы", "parent": cars},
        )
        Category.objects.get_or_create(
            slug="cars_bought",
            defaults={"name": "Выкупленные", "parent": cars},
        )
        text = (
            "[Название автомобиля] Geely Monjaro\n"
            "【Марка】 Geely\n"
            "【Категория】 Выкупленные\n"
            "【Тип кузова】 Кроссовер\n"
            "[Пробег] 15000 километров\n"
            "Цена 2 500 000 ₽"
        )
        result = ingest_listing(text)
        self.assertEqual(result.vehicle.category_id, crossover.id)
        self.assertTrue(result.vehicle.is_featured)
        self.assertEqual(result.vehicle.body_type, "Кроссовер")

    def test_ingest_attaches_photos_as_cover_and_gallery(self):
        import tempfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        from catalog.listing_ingest import ingest_listing

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        media = override_settings(MEDIA_ROOT=tmp.name)
        media.enable()
        self.addCleanup(media.disable)

        buf = BytesIO()
        Image.new("RGB", (80, 60), (10, 20, 30)).save(buf, format="JPEG")
        photo = SimpleUploadedFile(
            "cover.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        result = ingest_listing(self.SAMPLE, uploads=[photo])
        self.assertEqual(result.photos_added, 1)
        self.assertTrue(result.vehicle.main_image)
        self.assertEqual(result.vehicle.gallery.count(), 1)
        result.vehicle.main_image.close()
        for item in result.vehicle.gallery.all():
            item.image.close()

    def test_ingest_long_title_with_photos_fits_image_path(self):
        import tempfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        from catalog.listing_ingest import ingest_listing
        from catalog.models import VEHICLE_SLUG_MAX_LENGTH

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        media = override_settings(MEDIA_ROOT=tmp.name)
        media.enable()
        self.addCleanup(media.disable)

        long_title = (
            "Модель Haval Haval M6 Plus 2021 1.5T DCT "
            "Люксовая интеллектуальная комплектация 2023 "
            + ("очень длинное название " * 8)
        )
        text = (
            f"[Название автомобиля] {long_title}\n"
            "[Марка] Haval\n"
            "[Пробег] 12 000 километров\n"
            "【Цвет】 белый"
        )
        buf = BytesIO()
        Image.new("RGB", (80, 60), (10, 20, 30)).save(buf, format="JPEG")
        photo = SimpleUploadedFile(
            "cover_with_a_very_long_original_filename_from_phone_export.jpg",
            buf.getvalue(),
            content_type="image/jpeg",
        )
        result = ingest_listing(text, uploads=[photo])
        self.assertLessEqual(len(result.vehicle.slug), VEHICLE_SLUG_MAX_LENGTH)
        self.assertTrue(result.vehicle.main_image)
        self.assertLessEqual(len(result.vehicle.main_image.name), 255)
        self.assertEqual(result.photos_added, 1)
        result.vehicle.main_image.close()
        for item in result.vehicle.gallery.all():
            self.assertLessEqual(len(item.image.name), 255)
            item.image.close()

    def test_admin_ingest_page_renders(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from catalog.admin import VehicleAdmin

        user = get_user_model().objects.create_superuser(
            "ingest-admin", "ingest@example.com", "pass-not-used"
        )
        request = RequestFactory().get("/admin/catalog/vehicle/ingest-listing/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = VehicleAdmin(Vehicle, AdminSite()).ingest_listing_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Заполнить из комплектации")
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="photos"')

    def test_admin_ingest_post_creates_draft(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from catalog.admin import VehicleAdmin

        user = get_user_model().objects.create_superuser(
            "ingest-post", "ingest-post@example.com", "pass-not-used"
        )
        request = RequestFactory().post(
            "/admin/catalog/vehicle/ingest-listing/",
            {
                "description": self.SAMPLE,
                "category": "",
            },
        )
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = VehicleAdmin(Vehicle, AdminSite()).ingest_listing_view(request)
        self.assertEqual(response.status_code, 302)
        vehicle = Vehicle.objects.latest("id")
        self.assertIn("Volkswagen", vehicle.title)
        self.assertFalse(vehicle.is_published)

    def test_admin_ingest_rejects_too_many_photos_gracefully(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory
        from django.utils.datastructures import MultiValueDict
        from io import BytesIO
        from PIL import Image

        from catalog.admin import VehicleAdmin
        from catalog.listing_ingest import MAX_GALLERY_UPLOADS

        user = get_user_model().objects.create_superuser(
            "ingest-many", "ingest-many@example.com", "pass-not-used"
        )
        files = []
        for i in range(MAX_GALLERY_UPLOADS + 1):
            buf = BytesIO()
            Image.new("RGB", (20, 20), (i % 255, 10, 20)).save(buf, format="JPEG")
            files.append(
                SimpleUploadedFile(
                    f"p{i}.jpg", buf.getvalue(), content_type="image/jpeg"
                )
            )
        request = RequestFactory().post(
            "/admin/catalog/vehicle/ingest-listing/",
            {"description": self.SAMPLE, "category": ""},
        )
        _ = request.POST  # finish multipart parse before injecting files
        request._files = MultiValueDict({"photos": files})
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        before = Vehicle.objects.count()
        response = VehicleAdmin(Vehicle, AdminSite()).ingest_listing_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Vehicle.objects.count(), before)
        self.assertContains(response, "не больше")


class UploadErrorHandlerTests(TestCase):
    def test_too_many_files_shows_russian_message(self):
        from django.core.exceptions import TooManyFilesSent
        from django.test import RequestFactory, override_settings

        from core.errors import bad_request

        request = RequestFactory().post("/admin/catalog/vehicle/ingest-listing/")
        with override_settings(DATA_UPLOAD_MAX_NUMBER_FILES=40):
            response = bad_request(request, TooManyFilesSent("too many"))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Слишком много файлов", status_code=400)
        self.assertContains(response, "40", status_code=400)

    def test_request_too_big_shows_russian_message(self):
        from django.core.exceptions import RequestDataTooBig
        from django.test import RequestFactory

        from core.errors import bad_request

        request = RequestFactory().post("/admin/catalog/vehicle/ingest-listing/")
        response = bad_request(request, RequestDataTooBig("big"))
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "Размер запроса слишком большой", status_code=400
        )


@override_settings(RATELIMIT_ENABLE=False, SEO_MODEL_PAGES_ENABLED=True)
class SeoModelPagesTests(TestCase):
    def setUp(self):
        self.brand, _ = Brand.objects.get_or_create(
            slug="zeekr",
            defaults={"name": "Zeekr", "seo_landing_enabled": True},
        )
        self.other_brand, _ = Brand.objects.get_or_create(
            slug="li-auto",
            defaults={"name": "Li Auto", "seo_landing_enabled": True},
        )
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        self.car_model = CarModel.objects.create(
            brand=self.brand,
            name="001",
            slug="001",
            is_published=True,
        )
        CarModel.objects.create(
            brand=self.brand,
            name="007",
            slug="007",
            is_published=True,
        )
        self.vehicle = Vehicle.objects.create(
            title="Zeekr 001 2024",
            brand=self.brand,
            category=self.category,
            model="001",
            year=2024,
            mileage=1200,
            price_rub=4500000,
            is_published=True,
            slug="zeekr-001-stock",
        )
        Vehicle.objects.create(
            title="Zeekr 007 2024",
            brand=self.brand,
            category=self.category,
            model="007",
            year=2024,
            mileage=0,
            price_rub=4000000,
            is_published=True,
            slug="zeekr-007-stock",
        )

    def test_brands_index_lists_seo_brands(self):
        response = self.client.get(reverse("catalog:brands_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zeekr")
        self.assertContains(response, "Марки автомобилей из Китая")

    def test_model_page_with_stock(self):
        url = reverse(
            "catalog:model",
            kwargs={"brand_slug": "zeekr", "model_slug": "001"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zeekr 001 из Китая")
        self.assertContains(response, "Zeekr 001 2024")
        self.assertContains(response, "007")

    def test_model_page_without_stock(self):
        empty_model = CarModel.objects.create(
            brand=self.other_brand,
            name="L6",
            slug="l6",
            is_published=True,
        )
        url = reverse(
            "catalog:model",
            kwargs={"brand_slug": "li-auto", "model_slug": "l6"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Li Auto L6 из Китая")
        self.assertContains(response, "Готовых предложений по Li Auto L6 пока нет")
        self.assertContains(response, "работаем с дилерами")

    def test_brand_page_shows_model_chips(self):
        response = self.client.get(
            reverse("catalog:brand", kwargs={"brand_slug": "zeekr"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Модели:")
        self.assertContains(response, reverse("catalog:model", kwargs={"brand_slug": "zeekr", "model_slug": "001"}))

    def test_footer_link_when_enabled(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Марки авто")
        self.assertContains(response, reverse("catalog:brands_index"))

    @override_settings(SEO_MODEL_PAGES_ENABLED=False)
    def test_feature_flag_redirects_seo_routes(self):
        response = self.client.get(reverse("catalog:brands_index"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("catalog:category", kwargs={"category_slug": "cars"}))

        response = self.client.get(
            reverse(
                "catalog:model",
                kwargs={"brand_slug": "zeekr", "model_slug": "001"},
            )
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(SEO_MODEL_PAGES_ENABLED=False)
    def test_footer_link_hidden_when_disabled(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Марки авто")

    def test_model_in_sitemap_when_enabled(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("/catalog/brand/zeekr/model/001/", body)
        self.assertIn("/catalog/brands/", body)

    def test_seeded_directory_brand_without_stock(self):
        byd, _ = Brand.objects.get_or_create(
            slug="byd",
            defaults={"name": "BYD", "seo_landing_enabled": True},
        )
        Vehicle.objects.filter(brand=byd, is_published=True).update(is_published=False)
        response = self.client.get(reverse("catalog:brands_index"))
        self.assertContains(response, "BYD")
        response = self.client.get(reverse("catalog:brand", kwargs={"brand_slug": "byd"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BYD из Китая")
        self.assertContains(response, "BYD пока не в каталоге")
        self.assertContains(response, "работаем с дилерами")

    def test_unknown_brand_slug_404(self):
        response = self.client.get(
            reverse("catalog:brand", kwargs={"brand_slug": "nonexistent-brand"})
        )
        self.assertEqual(response.status_code, 404)


class AvitoPriceSyncTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Haval", slug="haval-avito")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        # Avoid hitting Redis when signals fire during fixture saves.
        self._delay_patch = patch("catalog.tasks.sync_avito_price_task.delay")
        self.mock_delay = self._delay_patch.start()
        self.addCleanup(self._delay_patch.stop)

    def test_parse_avito_item_id_from_url_and_digits(self):
        from catalog.avito import parse_avito_item_id

        self.assertEqual(parse_avito_item_id("1234567890"), 1234567890)
        self.assertEqual(
            parse_avito_item_id(
                "https://www.avito.ru/blagoveshchensk/avtomobili/haval_m6_1234567890"
            ),
            1234567890,
        )
        self.assertEqual(
            parse_avito_item_id(
                "https://www.avito.ru/moskva/avtomobili/item_999888777?utm=1"
            ),
            999888777,
        )
        self.assertIsNone(parse_avito_item_id(""))
        self.assertIsNone(parse_avito_item_id("not-an-id"))

    @override_settings(AVITO_CLIENT_ID="cid", AVITO_CLIENT_SECRET="sec")
    def test_update_item_price_posts_expected_body(self):
        from unittest.mock import MagicMock, patch as mock_patch

        from catalog.avito import clear_token_cache, update_item_price

        clear_token_cache()
        token_resp = MagicMock()
        token_resp.ok = True
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "tok-1",
            "expires_in": 86400,
        }

        price_resp = MagicMock()
        price_resp.ok = True
        price_resp.status_code = 200
        price_resp.content = b"{}"
        price_resp.json.return_value = {}

        with mock_patch("catalog.avito.requests.post") as mock_post:
            mock_post.side_effect = [token_resp, price_resp]
            update_item_price(1234567890, 2_500_000)

        self.assertEqual(mock_post.call_count, 2)
        price_call = mock_post.call_args_list[1]
        self.assertIn("/core/v1/items/1234567890/update_price", price_call.args[0])
        self.assertEqual(price_call.kwargs["json"], {"price": 2500000})
        self.assertIn("Bearer tok-1", price_call.kwargs["headers"]["Authorization"])
        token_call = mock_post.call_args_list[0]
        self.assertTrue(str(token_call.args[0]).rstrip("/").endswith("api.avito.ru/token"))

    @override_settings(AVITO_CLIENT_ID="", AVITO_CLIENT_SECRET="")
    def test_task_noop_without_credentials(self):
        from catalog.tasks import sync_avito_price_task

        vehicle = Vehicle.objects.create(
            title="No Creds",
            brand=self.brand,
            category=self.category,
            year=2022,
            price_rub=1000000,
            avito_item_id=111222333,
            slug="no-creds-avito",
        )
        self.assertFalse(sync_avito_price_task(vehicle.pk))

    @override_settings(AVITO_CLIENT_ID="cid", AVITO_CLIENT_SECRET="sec")
    def test_post_save_enqueues_only_when_price_changes(self):
        vehicle = Vehicle.objects.create(
            title="Sync Car",
            brand=self.brand,
            category=self.category,
            year=2023,
            price_rub=1_000_000,
            avito_item_id=555666777,
            slug="sync-car-avito",
        )
        self.mock_delay.assert_called()
        self.mock_delay.reset_mock()

        vehicle.title = "Sync Car Renamed"
        vehicle.save()
        self.mock_delay.assert_not_called()

        vehicle.price_rub = 1_100_000
        vehicle.save()
        self.mock_delay.assert_called_once_with(vehicle.pk)

    @override_settings(AVITO_CLIENT_ID="cid", AVITO_CLIENT_SECRET="sec")
    def test_linking_avito_id_enqueues_without_price_change(self):
        vehicle = Vehicle.objects.create(
            title="Link Later",
            brand=self.brand,
            category=self.category,
            year=2023,
            price_rub=2_000_000,
            slug="link-later-avito",
        )
        self.mock_delay.reset_mock()
        vehicle.avito_item_id = 888777666
        vehicle.save()
        self.mock_delay.assert_called_once_with(vehicle.pk)

    @override_settings(AVITO_CLIENT_ID="cid", AVITO_CLIENT_SECRET="sec")
    def test_task_writes_sync_timestamp(self):
        from unittest.mock import patch as mock_patch

        from catalog.tasks import sync_avito_price_task

        vehicle = Vehicle.objects.create(
            title="Priced Car",
            brand=self.brand,
            category=self.category,
            year=2021,
            price_rub=3_000_000,
            avito_item_id=444555666,
            slug="priced-car-avito",
        )
        with mock_patch("catalog.avito.update_item_price", return_value={}):
            self.assertTrue(sync_avito_price_task(vehicle.pk))
        vehicle.refresh_from_db()
        self.assertIsNotNone(vehicle.avito_price_synced_at)
        self.assertEqual(vehicle.avito_price_sync_error, "")

