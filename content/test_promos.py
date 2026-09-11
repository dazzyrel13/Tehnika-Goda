from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from content.models import PromoBanner
from content.promos import resync_default_promos


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

    def test_resync_replace_all_dedupes(self):
        for i in range(3):
            b = PromoBanner(
                title="Авто в кредит",
                teaser="dup",
                is_published=True,
                sort_order=i,
            )
            b.image.save(
                f"dup{i}.png",
                SimpleUploadedFile(
                    f"dup{i}.png", _png_bytes(), content_type="image/png"
                ),
                save=False,
            )
            b.save()

        base = Path(settings.BASE_DIR) / "data" / "promos"
        if not (base / "credit.webp").exists():
            self.skipTest("data/promos/credit.webp missing")
        count = resync_default_promos(replace_all=True)
        self.assertEqual(count, 2)
        self.assertEqual(PromoBanner.objects.count(), 2)
        self.assertEqual(
            list(
                PromoBanner.objects.order_by("sort_order").values_list(
                    "title", flat=True
                )
            ),
            ["Авто в кредит", "Зимние шины в подарок"],
        )
