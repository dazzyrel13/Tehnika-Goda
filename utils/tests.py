from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from utils.client_ip import (
    get_client_ip,
    get_client_ip_for_axes,
    get_client_ip_for_ratelimit,
)
from utils.html_sanitize import sanitize_html
from utils.pdf_validate import validate_pdf_upload
from utils.safe_http import _is_disallowed_ip, is_safe_request_url


class HtmlSanitizeTests(SimpleTestCase):
    def test_strips_script_tags(self):
        dirty = "<p>ok</p><script>alert(1)</script>"
        clean = sanitize_html(dirty)
        self.assertIn("<p>ok</p>", clean)
        self.assertNotIn("script", clean.lower())

    def test_keeps_allowed_links(self):
        html = '<a href="https://example.com" title="x">link</a>'
        self.assertIn('href="https://example.com"', sanitize_html(html))

    def test_blank_target_gets_noopener(self):
        html = '<a href="https://example.com" target="_blank">x</a>'
        clean = sanitize_html(html)
        self.assertIn("noopener", clean)
        self.assertIn("noreferrer", clean)

    def test_strips_global_class(self):
        html = '<p class="evil">x</p>'
        clean = sanitize_html(html)
        self.assertNotIn("class=", clean)

    def test_empty_input(self):
        self.assertEqual(sanitize_html(""), "")
        self.assertEqual(sanitize_html(None), "")

    def test_strips_remote_images(self):
        html = '<p>x</p><img src="https://evil.example/a.png" alt="x"><img src="/media/ok.webp" alt="y">'
        clean = sanitize_html(html)
        self.assertNotIn("evil.example", clean)
        self.assertIn('src="/media/ok.webp"', clean)


class SafeHttpTests(SimpleTestCase):
    def test_rejects_non_http_schemes(self):
        self.assertFalse(is_safe_request_url("file:///etc/passwd"))
        self.assertFalse(is_safe_request_url("ftp://example.com/a"))

    def test_rejects_credentials_in_url(self):
        self.assertFalse(is_safe_request_url("https://user:pass@example.com/"))

    def test_rejects_missing_host(self):
        self.assertFalse(is_safe_request_url("https:///path"))

    def test_rejects_loopback_hostname(self):
        self.assertFalse(is_safe_request_url("http://127.0.0.1/secret"))
        self.assertFalse(is_safe_request_url("http://localhost/secret"))

    def test_rejects_ipv4_mapped_loopback(self):
        self.assertFalse(is_safe_request_url("http://[::ffff:127.0.0.1]/secret"))
        self.assertFalse(is_safe_request_url("http://[::ffff:169.254.169.254]/latest"))

    def test_rejects_integer_ipv4_literal(self):
        self.assertFalse(is_safe_request_url("http://2130706433/secret"))
        self.assertFalse(is_safe_request_url("http://0x7f000001/secret"))

    def test_disallowed_ip_unwraps_mapped_ipv6(self):
        import ipaddress

        self.assertTrue(_is_disallowed_ip(ipaddress.ip_address("::ffff:127.0.0.1")))
        self.assertTrue(_is_disallowed_ip(ipaddress.ip_address("::ffff:10.0.0.1")))
        self.assertTrue(_is_disallowed_ip(ipaddress.ip_address("::ffff:169.254.169.254")))
        self.assertFalse(_is_disallowed_ip(ipaddress.ip_address("8.8.8.8")))
        self.assertFalse(_is_disallowed_ip(ipaddress.ip_address("::ffff:8.8.8.8")))


class ClientIpTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BEHIND_HTTPS_PROXY=False, TRUST_PROXY_HEADERS=False)
    def test_ignores_spoofed_xff_without_proxy_trust(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        self.assertEqual(get_client_ip(request), "10.0.0.5")

    @override_settings(BEHIND_HTTPS_PROXY=True, TRUST_PROXY_HEADERS=True)
    def test_prefers_x_real_ip(self):
        request = self.factory.get(
            "/",
            HTTP_X_REAL_IP="203.0.113.10",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.10",
        )
        request.META["REMOTE_ADDR"] = "172.18.0.1"
        self.assertEqual(get_client_ip(request), "203.0.113.10")

    @override_settings(BEHIND_HTTPS_PROXY=True)
    def test_xff_uses_rightmost_hop(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.20")
        request.META["REMOTE_ADDR"] = "172.18.0.1"
        self.assertEqual(get_client_ip(request), "198.51.100.20")

    def test_ratelimit_helper_never_empty(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = ""
        self.assertEqual(get_client_ip_for_ratelimit(request), "0.0.0.0")

    def test_axes_helper_never_empty(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = ""
        self.assertEqual(get_client_ip_for_axes(request), "0.0.0.0")

    @override_settings(BEHIND_HTTPS_PROXY=True, TRUST_PROXY_HEADERS=True)
    def test_ignores_x_real_ip_from_public_peer(self):
        request = self.factory.get("/", HTTP_X_REAL_IP="203.0.113.10")
        request.META["REMOTE_ADDR"] = "8.8.8.8"
        self.assertEqual(get_client_ip(request), "8.8.8.8")

    @override_settings(
        TESTING=False, BEHIND_HTTPS_PROXY=True, TRUST_PROXY_HEADERS=True
    )
    def test_loopback_ignores_spoofed_header_outside_tests(self):
        request = self.factory.get("/", HTTP_X_REAL_IP="203.0.113.10")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        self.assertEqual(get_client_ip(request), "127.0.0.1")


class PdfValidateTests(SimpleTestCase):
    def test_rejects_non_pdf_extension(self):
        upload = SimpleUploadedFile("evil.html", b"<html>x</html>")
        with self.assertRaises(ValidationError):
            validate_pdf_upload(upload)

    def test_rejects_wrong_magic(self):
        upload = SimpleUploadedFile("fake.pdf", b"not-a-pdf")
        with self.assertRaises(ValidationError):
            validate_pdf_upload(upload)

    def test_accepts_pdf_magic(self):
        upload = SimpleUploadedFile("ok.pdf", b"%PDF-1.4\n%")
        validate_pdf_upload(upload)


class SeoHelpersTests(SimpleTestCase):
    @override_settings(SITE_URL="https://tehnikagoda.ru")
    def test_absolute_url_and_domain(self):
        from utils.seo import absolute_url, site_domain, site_protocol

        self.assertEqual(site_protocol(), "https")
        self.assertEqual(site_domain(), "tehnikagoda.ru")
        self.assertEqual(absolute_url("/catalog/"), "https://tehnikagoda.ru/catalog/")

    @override_settings(SITE_URL="https://tehnikagoda.ru")
    def test_canonical_strips_utm(self):
        from utils.seo import canonical_url_for_request

        request = RequestFactory().get("/catalog/cars/?category=cars&utm_source=yandex")
        self.assertEqual(
            canonical_url_for_request(request),
            "https://tehnikagoda.ru/catalog/cars/?category=cars",
        )

    def test_listing_filter_noindex_rules(self):
        from catalog.seo_copy import has_extra_listing_filters

        self.assertFalse(
            has_extra_listing_filters(
                {}, path_has_category=True, path_has_brand=False
            )
        )
        self.assertTrue(
            has_extra_listing_filters(
                {"page": "2"}, path_has_category=True, path_has_brand=False
            )
        )
        self.assertTrue(
            has_extra_listing_filters(
                {"brand": "bmw"}, path_has_category=True, path_has_brand=False
            )
        )
        self.assertTrue(
            has_extra_listing_filters(
                {"price_from": "1"}, path_has_category=True, path_has_brand=False
            )
        )


@override_settings(SITE_URL="https://tehnikagoda.ru")
class SitemapDomainTests(TestCase):
    def test_sitemap_uses_site_url_domain(self):
        from catalog.models import Brand, Category, Vehicle

        brand = Brand.objects.create(name="SEOBrand", slug="seo-brand")
        category = Category.objects.create(name="SEOCat", slug="seo-cat")
        Vehicle.objects.create(
            title="SEO Car",
            brand=brand,
            category=category,
            year=2024,
            mileage=0,
            is_published=True,
            slug="seo-car",
        )
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("https://tehnikagoda.ru/", body)
        self.assertNotIn("example.com", body)
        self.assertIn("/catalog/category/seo-cat/", body)
        self.assertIn("/catalog/brand/seo-brand/", body)
        self.assertIn("/catalog/vehicle/seo-car/", body)

        # Empty categories stay out of the sitemap.
        Category.objects.create(name="Empty", slug="empty-cat")
        body2 = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("/catalog/category/empty-cat/", body2)

    def test_home_has_canonical_and_og(self):
        from django.urls import reverse

        response = self.client.get(reverse("catalog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="canonical"')
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card"')
        self.assertContains(response, "https://tehnikagoda.ru/catalog/")


class ImageProcessingTests(SimpleTestCase):
    def _upload(self, width, height, name, fmt="JPEG"):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (width, height), (20, 90, 160)).save(buf, format=fmt)
        buf.seek(0)
        mime = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
        return SimpleUploadedFile(name, buf.read(), content_type=mime)

    def test_jpeg_converts_and_downscales(self):
        from PIL import Image

        from utils.image_processing import process_image_to_webp

        processed = process_image_to_webp(self._upload(2000, 1000, "wide.jpg"))
        self.assertIsNotNone(processed)
        self.assertTrue(processed.name.endswith(".webp"))
        img = Image.open(processed)
        self.assertEqual(img.width, 1600)
        self.assertEqual(img.format, "WEBP")

    def test_small_webp_is_not_recompressed(self):
        from utils.image_processing import process_image_to_webp

        upload = self._upload(800, 500, "ok.webp", fmt="WEBP")
        self.assertIsNone(process_image_to_webp(upload))

    def test_oversized_webp_is_resized(self):
        from PIL import Image

        from utils.image_processing import process_image_to_webp

        processed = process_image_to_webp(
            self._upload(2400, 1200, "huge.webp", fmt="WEBP")
        )
        self.assertIsNotNone(processed)
        self.assertEqual(Image.open(processed).width, 1600)

    def test_variants_and_srcset(self):
        import tempfile
        from io import BytesIO
        from types import SimpleNamespace

        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage
        from PIL import Image

        from django.core.cache import cache

        from utils.image_processing import (
            responsive_attrs,
            variant_storage_name,
            write_responsive_variants,
        )

        cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        storage = FileSystemStorage(location=tmp.name, base_url="/media/")
        buf = BytesIO()
        Image.new("RGB", (1600, 900), (30, 30, 30)).save(buf, format="WEBP")
        buf.seek(0)
        storage.save("cars/main.webp", ContentFile(buf.read()))
        field = SimpleNamespace(
            name="cars/main.webp",
            storage=storage,
            url="/media/cars/main.webp",
        )
        write_responsive_variants(field)
        self.assertTrue(storage.exists(variant_storage_name("cars/main.webp", 400)))
        self.assertTrue(storage.exists(variant_storage_name("cars/main.webp", 800)))
        attrs = responsive_attrs(field, default_width=800)
        self.assertIn(".w800.webp", attrs["src"])
        self.assertIn("400w", attrs["srcset"])
        self.assertIn("800w", attrs["srcset"])
        self.assertEqual(attrs["full_src"], "/media/cars/main.webp")
        self.assertIn("1600w", attrs["srcset"])

    def test_srcset_uses_actual_master_width(self):
        import tempfile
        from io import BytesIO
        from types import SimpleNamespace
        from unittest.mock import patch

        from django.core.cache import cache
        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage
        from PIL import Image

        from utils.image_processing import responsive_attrs, write_responsive_variants

        cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        storage = FileSystemStorage(location=tmp.name, base_url="/media/")
        buf = BytesIO()
        Image.new("RGB", (900, 500), (30, 30, 30)).save(buf, format="WEBP")
        buf.seek(0)
        storage.save("cars/narrow.webp", ContentFile(buf.read()))
        field = SimpleNamespace(
            name="cars/narrow.webp",
            storage=storage,
            url="/media/cars/narrow.webp",
        )
        write_responsive_variants(field)
        attrs = responsive_attrs(field, default_width=800)
        self.assertIn("900w", attrs["srcset"])
        self.assertNotIn("1600w", attrs["srcset"])
        self.assertIn("400w", attrs["srcset"])
        with patch.object(storage, "exists") as exists:
            again = responsive_attrs(field, default_width=800)
            exists.assert_not_called()
        self.assertEqual(again["srcset"], attrs["srcset"])

