from django.test import RequestFactory, TestCase
from django.urls import reverse

from catalog.cache_helpers import invalidate_home_reviews_cache, review_platforms

from .models import Review
from .sitemaps import StaticViewSitemap
from .views import FAQListView


class FAQPagesTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_faq_list_renders(self):
        request = self.factory.get("/content/faq/")
        response = FAQListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        response.render()


class StaticSitemapTests(TestCase):
    def test_static_sitemap_url_names_resolve(self):
        sm = StaticViewSitemap()
        for item in sm.items():
            path = sm.location(item)
            self.assertTrue(path.startswith("/"), msg=path)
            self.assertNotIn("blog", path)

    def test_services_page_in_sitemap(self):
        sm = StaticViewSitemap()
        paths = [sm.location(item) for item in sm.items()]
        self.assertIn("/services/", paths)


class ServicesPageTests(TestCase):
    def test_services_page_renders_price_example(self):
        response = self.client.get(reverse("services"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Информация об услугах и прайс-лист")
        self.assertContains(response, "Honda XR-V")
        self.assertContains(response, "1&nbsp;680&nbsp;000")
        self.assertContains(response, "года выпуска")
        self.assertContains(response, "типа двигателя")
        self.assertContains(response, "Оставить заявку")

    def test_services_page_has_article_json_ld(self):
        response = self.client.get(reverse("services"))
        self.assertContains(response, '"@type":"Article"')
        self.assertContains(response, '"datePublished":"2025-03-01"')


class InfoPagesArticleJsonLdTests(TestCase):
    def test_info_pages_expose_article_json_ld(self):
        pages = (
            ("about", "О компании Техника Года"),
            ("leasing", "Лизинг коммерческого транспорта и спецтехники"),
            ("privacy", "Политика конфиденциальности"),
        )
        for url_name, headline in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '"@type":"Article"')
                self.assertContains(response, f'"headline":"{headline}"')
                self.assertContains(response, '"datePublished"')

    def test_faq_page_has_article_json_ld(self):
        response = self.client.get(reverse("content:faq"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"@type":"Article"')
        self.assertContains(response, '"@type": "FAQPage"')
        self.assertContains(response, "FAQ по покупке авто из Китая")


class ReviewPlatformStatsTests(TestCase):
    def setUp(self):
        invalidate_home_reviews_cache()

    def test_empty_reviews_show_no_fake_scores(self):
        platforms = {p["key"]: p for p in review_platforms()}
        for key in ("yandex", "2gis", "avito"):
            self.assertEqual(platforms[key]["score"], "—")
            self.assertFalse(platforms[key]["has_rating"])
            self.assertEqual(platforms[key]["count"], 0)
            self.assertIn("пока нет оценок", platforms[key]["label"])

    def test_averages_from_published_reviews(self):
        Review.objects.create(
            client_name="Иван",
            comment="Отлично",
            rating=5,
            source=Review.SOURCE_YANDEX,
            is_published=True,
        )
        Review.objects.create(
            client_name="Пётр",
            comment="Хорошо",
            rating=3,
            source=Review.SOURCE_YANDEX,
            is_published=True,
        )
        Review.objects.create(
            client_name="Hidden",
            comment="Не видно",
            rating=1,
            source=Review.SOURCE_YANDEX,
            is_published=False,
        )
        Review.objects.create(
            client_name="Анна",
            comment="2ГИС",
            rating=4,
            source=Review.SOURCE_2GIS,
            is_published=True,
        )
        invalidate_home_reviews_cache()
        platforms = {p["key"]: p for p in review_platforms()}
        self.assertEqual(platforms["yandex"]["score"], "4.0")
        self.assertEqual(platforms["yandex"]["count"], 2)
        self.assertTrue(platforms["yandex"]["has_rating"])
        self.assertIn("2 оценки", platforms["yandex"]["label"])
        self.assertEqual(platforms["2gis"]["score"], "4.0")
        self.assertEqual(platforms["2gis"]["count"], 1)
        self.assertEqual(platforms["avito"]["score"], "—")
        self.assertEqual(platforms["avito"]["count"], 0)

    def test_platform_urls_from_admin_settings(self):
        from content.models import ReviewPlatformSettings

        settings_obj = ReviewPlatformSettings.load()
        settings_obj.yandex_url = "https://yandex.ru/maps/org/test"
        settings_obj.twogis_url = "https://2gis.ru/firm/test"
        settings_obj.avito_url = "https://www.avito.ru/user/test"
        settings_obj.save()
        invalidate_home_reviews_cache()
        platforms = {p["key"]: p for p in review_platforms()}
        self.assertEqual(platforms["yandex"]["url"], "https://yandex.ru/maps/org/test")
        self.assertEqual(platforms["2gis"]["url"], "https://2gis.ru/firm/test")
        self.assertEqual(platforms["avito"]["url"], "https://www.avito.ru/user/test")
