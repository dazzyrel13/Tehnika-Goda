from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from io import BytesIO

from content.models import PromoBanner


def _png_bytes(size=200):
    buf = BytesIO()
    Image.new("RGB", (size, size), color=(240, 180, 40)).save(buf, format="PNG")
    return buf.getvalue()


class PromoBannerTests(TestCase):
    def test_save_converts_image_to_webp(self):
        banner = PromoBanner(
            title="Тест акция",
            teaser="Короткий текст",
            link_url="#leads-section",
            sort_order=1,
        )
        banner.image.save(
            "promo.png",
            SimpleUploadedFile("promo.png", _png_bytes(), content_type="image/png"),
            save=False,
        )
        banner.save()
        banner.refresh_from_db()
        self.assertTrue(banner.image.name.lower().endswith(".webp"))

    def test_home_shows_published_promos(self):
        banner = PromoBanner(
            title="Зимние шины в подарок",
            teaser="До 30 сентября",
            is_published=True,
            sort_order=1,
        )
        banner.image.save(
            "tires.png",
            SimpleUploadedFile("tires.png", _png_bytes(), content_type="image/png"),
            save=False,
        )
        banner.save()
        hidden = PromoBanner(
            title="Скрытая",
            teaser="Не показывать",
            is_published=False,
            sort_order=2,
        )
        hidden.image.save(
            "hidden.png",
            SimpleUploadedFile("hidden.png", _png_bytes(), content_type="image/png"),
            save=False,
        )
        hidden.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Акции")
        self.assertContains(response, "Зимние шины в подарок")
        self.assertContains(response, "До 30 сентября")
        self.assertNotContains(response, "Скрытая")
