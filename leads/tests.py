import time
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Inquiry
from .validators import normalize_ru_phone


def _valid_payload(**overrides):
    data = {
        "name": "Иван",
        "phone": "+79991234567",
        "city": "Москва",
        "message": "Тестовая заявка",
        "form_ts": str(time.time() - 5),
    }
    data.update(overrides)
    return data


@override_settings(RATELIMIT_ENABLE=False, TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
@patch("leads.tasks.send_inquiry_telegram_task.delay")
class LeadsViewsTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_submit_inquiry_ajax_success(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(Inquiry.objects.count(), 1)
        self.assertEqual(Inquiry.objects.get().phone, "+79991234567")
        _notify.assert_called_once()
        self.assertEqual(_notify.call_args.args[0], Inquiry.objects.get().pk)

    def test_submit_inquiry_ajax_validation_error(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(phone="invalid-number"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "error")

    def test_submit_inquiry_ajax_city_required(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(city=""),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("city", payload["errors"])

    def test_submit_inquiry_ajax_allows_empty_message(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(message=""),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_submit_inquiry_ajax_repeat_phone_blocked(self, _notify):
        self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(message="First"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        second = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(message="Second"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        self.assertEqual(second.status_code, 429)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_submit_inquiry_saves_utm_from_post(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(
                phone="89990001122",
                message="UTM test",
                utm_source="yandex",
                utm_medium="cpc",
                utm_campaign="spring",
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.phone, "+79990001122")
        self.assertEqual(inquiry.utm_source, "yandex")
        self.assertEqual(inquiry.utm_medium, "cpc")
        self.assertEqual(inquiry.utm_campaign, "spring")

    def test_rejects_foreign_phone_clara_style(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(
                name="Clara Rihtter",
                phone="+1785738457785",
                city="New York",
                message="supergirl@rambler.com",
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_rejects_latin_name_even_with_ru_phone(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(name="Clara Rihtter", city="Москва"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_rejects_email_in_message(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(message="Пишите на supergirl@rambler.com"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_rejects_bare_domain_in_message(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(message="Смотрите на avito.ru срочно"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_honeypot_soft_fails(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(website="http://spam.test"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_normalize_phone_from_8(self, _notify):
        self.assertEqual(normalize_ru_phone("8 (924) 149-00-13"), "+79241490013")

    def test_unpublished_vehicle_is_not_attached(self, _notify):
        from catalog.models import Brand, Category, Vehicle

        brand = Brand.objects.create(name="LeadBrand", slug="leadbrand")
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )
        hidden = Vehicle.objects.create(
            title="Hidden Car",
            brand=brand,
            category=category,
            year=2024,
            price_rub=1000000,
            is_published=False,
        )
        visible = Vehicle.objects.create(
            title="Visible Car",
            brand=brand,
            category=category,
            year=2024,
            price_rub=1000000,
            is_published=True,
        )
        hidden_resp = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(vehicle=str(hidden.pk), phone="+79991110001"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        self.assertEqual(hidden_resp.status_code, 200)
        self.assertIsNone(Inquiry.objects.get(phone="+79991110001").vehicle_id)

        from django.core.cache import cache

        cache.clear()
        visible_resp = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(vehicle=str(visible.pk), phone="+79991110002"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_REFERER="http://testserver/catalog/cars/",
        )
        self.assertEqual(visible_resp.status_code, 200)
        self.assertEqual(Inquiry.objects.get(phone="+79991110002").vehicle_id, visible.pk)

    def test_missing_form_ts_creates_inquiry(self, _notify):
        data = _valid_payload()
        data.pop("form_ts")
        response = self.client.post(
            reverse("leads:submit"),
            data=data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_instant_form_ts_soft_fails(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(form_ts=str(time.time())),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_small_clock_skew_allowed(self, _notify):
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(form_ts=str(time.time() + 30)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_save_failure_releases_cooldown(self, _notify):
        with patch.object(Inquiry, "save", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("leads:submit"),
                    data=_valid_payload(),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
        response = self.client.post(
            reverse("leads:submit"),
            data=_valid_payload(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 1)


class TelegramRedactTests(SimpleTestCase):
    def test_redacts_token_and_bot_path(self):
        from leads.telegram import _redact_secrets

        token = "123456:ABC-DEF"
        raw = (
            "404 Client Error: Not Found for url: "
            f"https://api.telegram.org/bot{token}/sendMessage"
        )
        out = _redact_secrets(raw, token)
        self.assertNotIn(token, out)
        self.assertIn("/bot***/", out)
