from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from leads.bitrix import _build_fields, _webhook_base, is_configured, send_inquiry_to_bitrix


class BitrixWebhookConfigTests(SimpleTestCase):
    @override_settings(BITRIX24_WEBHOOK_URL="")
    def test_empty_not_configured(self):
        self.assertFalse(is_configured())
        self.assertEqual(_webhook_base(), "")

    @override_settings(
        BITRIX24_WEBHOOK_URL="https://demo.bitrix24.ru/rest/1/abcsecrettoken/"
    )
    def test_valid_webhook(self):
        self.assertTrue(is_configured())
        self.assertEqual(
            _webhook_base(), "https://demo.bitrix24.ru/rest/1/abcsecrettoken/"
        )

    @override_settings(BITRIX24_WEBHOOK_URL="https://evil.example/rest/1/x/")
    def test_non_bitrix_host_still_ok_with_rest_path(self):
        # Custom Bitrix domain is allowed when /rest/ is present.
        self.assertTrue(is_configured())

    @override_settings(BITRIX24_WEBHOOK_URL="https://demo.bitrix24.ru/oauth/")
    def test_rejects_without_rest_path(self):
        self.assertFalse(is_configured())


class BitrixFieldsTests(SimpleTestCase):
    def test_build_fields_includes_phone_and_utm(self):
        inquiry = MagicMock()
        inquiry.pk = 42
        inquiry.name = "Иван"
        inquiry.phone = "+79991234567"
        inquiry.city = "Благовещенск"
        inquiry.message = "Нужен Zeekr"
        inquiry.source = "https://tehnikagoda.ru/catalog/"
        inquiry.utm_source = "yandex"
        inquiry.utm_medium = "cpc"
        inquiry.utm_campaign = "cars"
        inquiry.vehicle = None

        fields = _build_fields(inquiry)
        self.assertIn("Иван", fields["TITLE"])
        self.assertEqual(fields["NAME"], "Иван")
        self.assertEqual(fields["PHONE"][0]["VALUE"], "+79991234567")
        self.assertEqual(fields["SOURCE_ID"], "WEB")
        self.assertEqual(fields["UTM_SOURCE"], "yandex")
        self.assertIn("Благовещенск", fields["COMMENTS"])
        self.assertIn("42", fields["COMMENTS"])


@override_settings(
    BITRIX24_WEBHOOK_URL="https://demo.bitrix24.ru/rest/1/tokensecret/"
)
class BitrixSendTests(SimpleTestCase):
    @patch("leads.bitrix.requests.post")
    def test_send_success(self, post):
        post.return_value = MagicMock(
            ok=True, status_code=200, text='{"result":101}', json=lambda: {"result": 101}
        )
        inquiry = MagicMock(
            pk=7,
            name="Аня",
            phone="+79990001122",
            city="Хабаровск",
            message="",
            source="",
            utm_source="",
            utm_medium="",
            utm_campaign="",
            vehicle=None,
        )
        self.assertTrue(send_inquiry_to_bitrix(inquiry))
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith("crm.lead.add.json"))
        self.assertEqual(kwargs["json"]["fields"]["PHONE"][0]["VALUE"], "+79990001122")

    @patch("leads.bitrix.requests.post")
    def test_send_api_error(self, post):
        post.return_value = MagicMock(
            ok=True,
            status_code=200,
            text='{"error":"ACCESS_DENIED"}',
            json=lambda: {"error": "ACCESS_DENIED"},
        )
        inquiry = MagicMock(
            pk=8,
            name="Боб",
            phone="+79990003344",
            city="",
            message="",
            source="",
            utm_source="",
            utm_medium="",
            utm_campaign="",
            vehicle=None,
        )
        self.assertFalse(send_inquiry_to_bitrix(inquiry))
