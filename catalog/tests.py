from django.test import TestCase, override_settings
from django.urls import reverse

from .cache_helpers import invalidate_nav_cache
from .models import Brand, Category, Vehicle, VehicleImage


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

    def test_list_shows_published_only(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Car")
        self.assertNotContains(response, "Hidden Car")
        self.assertContains(response, "по курсу 12.48")

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
        self.assertContains(response, "mileageFromOdometer")
        self.assertContains(response, 'aria-label="Хлебные крошки"')
        self.assertContains(
            response,
            "Цена под ключ до Благовещенска по курсу 12.48. "
            "Актуальную цену на день заявки уточняйте у менеджера.",
        )
        self.assertNotContains(response, "Цена в карточке ориентировочная")

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

    def test_category_has_h1_and_indexable(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Легковые автомобили из Китая")
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
        self.brand = Brand.objects.create(name="FilterBrand", slug="filterbrand")
        self.new_car = Vehicle.objects.create(
            title="New Zero",
            brand=self.brand,
            category=self.cars,
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

    def test_cars_new_filter_mileage_zero(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_new"})
        )
        self.assertEqual(response.status_code, 200)
        titles = [v.title for v in response.context["vehicles"]]
        self.assertIn("New Zero", titles)
        self.assertNotIn("Used Plain", titles)

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

    def test_featured_zero_km_not_in_cars_new(self):
        Vehicle.objects.create(
            title="New Featured",
            brand=self.brand,
            category=self.cars,
            year=2025,
            mileage=0,
            is_published=True,
            is_featured=True,
            slug="new-featured",
            price_rub=3000000,
        )
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": "cars_new"})
        )
        titles = [v.title for v in response.context["vehicles"]]
        self.assertIn("New Zero", titles)
        self.assertNotIn("New Featured", titles)

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

    def test_badge_items_new_and_bought(self):
        from catalog.templatetags.catalog_extras import vehicle_badge_items

        new_badges = vehicle_badge_items(self.new_car)
        self.assertEqual([b["text"] for b in new_badges], ["Новый"])

        bought_badges = vehicle_badge_items(self.bought_flag)
        self.assertEqual([b["text"] for b in bought_badges], ["Выкупленные"])

        both = Vehicle.objects.create(
            title="Both",
            brand=self.brand,
            category=self.cars,
            year=2024,
            mileage=0,
            is_published=True,
            is_featured=True,
            slug="both-badges",
        )
        texts = [b["text"] for b in vehicle_badge_items(both)]
        self.assertEqual(texts, ["Новый", "Выкупленные"])
        self.assertNotIn("Рекомендуем", texts)

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


