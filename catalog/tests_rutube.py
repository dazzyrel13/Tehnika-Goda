from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Brand, Category, Vehicle
from catalog.rutube import parse_rutube_embed_url
from core.csp import build_public_csp


class RutubeParseTests(SimpleTestCase):
    def test_watch_url(self):
        self.assertEqual(
            parse_rutube_embed_url(
                "https://rutube.ru/video/48d4c504e46d01723a5bb920a064c383/"
            ),
            "https://rutube.ru/play/embed/48d4c504e46d01723a5bb920a064c383",
        )

    def test_embed_url_passthrough(self):
        self.assertEqual(
            parse_rutube_embed_url(
                "https://rutube.ru/play/embed/48d4c504e46d01723a5bb920a064c383"
            ),
            "https://rutube.ru/play/embed/48d4c504e46d01723a5bb920a064c383",
        )

    def test_private_token_kept(self):
        self.assertEqual(
            parse_rutube_embed_url(
                "https://rutube.ru/video/private/abc123def456/?p=TokenValue"
            ),
            "https://rutube.ru/play/embed/abc123def456?p=TokenValue",
        )

    def test_rejects_non_rutube(self):
        self.assertEqual(parse_rutube_embed_url("https://youtube.com/watch?v=x"), "")
        self.assertEqual(parse_rutube_embed_url(""), "")


class RutubeCspTests(SimpleTestCase):
    def test_frame_src_allows_rutube(self):
        csp = build_public_csp()
        self.assertRegex(csp, r"frame-src[^;]*https://rutube\.ru")
        self.assertRegex(csp, r"child-src[^;]*https://rutube\.ru")


@override_settings(RATELIMIT_ENABLE=False)
class RutubeDetailTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="RutubeBrand", slug="rutube-brand")
        cat = Category.objects.create(name="Cars", slug="cars-rutube")
        self.vehicle = Vehicle.objects.create(
            brand=brand,
            category=cat,
            title="Video Car",
            slug="video-car",
            year=2024,
            mileage=1000,
            price_rub=2500000,
            is_published=True,
            rutube_url="https://rutube.ru/play/embed/48d4c504e46d01723a5bb920a064c383",
        )

    def test_detail_embeds_rutube_iframe(self):
        response = self.client.get(
            reverse("catalog:vehicle_detail", kwargs={"slug": self.vehicle.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vehicle-video")
        self.assertContains(
            response,
            'src="https://rutube.ru/play/embed/48d4c504e46d01723a5bb920a064c383"',
        )
        self.assertContains(response, "Видеообзор")
