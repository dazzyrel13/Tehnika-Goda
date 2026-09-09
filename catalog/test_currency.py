from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from catalog.cbr import CbrRateError, fetch_cbr_cny_rate
from catalog.currency import FALLBACK_CNY_RATE, recalculate_all_cny_prices
from catalog.models import Brand, Category, CurrencyRateSettings, Vehicle


class CurrencyPricingTests(TestCase):
    def setUp(self):
        self.settings = CurrencyRateSettings.load()
        self.settings.manual_cny_rate = None
        self.settings.cbr_cny_rate = None
        self.settings.cbr_fetched_at = None
        self.settings.save()
        self.brand = Brand.objects.create(name="RateBrand", slug="ratebrand")
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Cars"}
        )

    def test_effective_rate_priority_manual_over_cbr_over_fallback(self):
        self.assertEqual(self.settings.effective_rate(), FALLBACK_CNY_RATE)
        self.settings.cbr_cny_rate = Decimal("11.11")
        self.settings.save()
        self.assertEqual(CurrencyRateSettings.load().effective_rate(), Decimal("11.11"))
        self.settings.manual_cny_rate = Decimal("13.50")
        self.settings.save()
        self.assertEqual(CurrencyRateSettings.load().effective_rate(), Decimal("13.50"))

    def test_cny_price_recalculates_rub_on_save(self):
        settings = CurrencyRateSettings.load()
        settings.manual_cny_rate = Decimal("12.00")
        settings.save()

        vehicle = Vehicle(
            title="CNY Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            price_cny=Decimal("100000.00"),
            slug="cny-car",
        )
        vehicle.save()
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.price_rub, Decimal("1200000"))
        self.assertEqual(vehicle.cny_rate, Decimal("12.00"))
        self.assertFalse(vehicle.is_currency_fixed)

    def test_rub_only_price_stays_fixed_when_rate_changes(self):
        vehicle = Vehicle.objects.create(
            title="Fixed Rub Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            price_rub=Decimal("1000000"),
            slug="fixed-rub-car",
        )
        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_currency_fixed)
        self.assertIsNone(vehicle.price_cny)

        settings = CurrencyRateSettings.load()
        settings.manual_cny_rate = Decimal("20.00")
        settings.save()
        recalculate_all_cny_prices()
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.price_rub, Decimal("1000000"))

    def test_recalculate_updates_cny_vehicles_only(self):
        settings = CurrencyRateSettings.load()
        settings.manual_cny_rate = Decimal("10.00")
        settings.save()
        cny_car = Vehicle.objects.create(
            title="Dyn Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            price_cny=Decimal("50000"),
            slug="dyn-car",
        )
        fixed = Vehicle.objects.create(
            title="Fix Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            price_rub=Decimal("999000"),
            slug="fix-car-2",
        )
        settings.manual_cny_rate = Decimal("12.00")
        settings.save()
        updated = recalculate_all_cny_prices()
        self.assertGreaterEqual(updated, 1)
        cny_car.refresh_from_db()
        fixed.refresh_from_db()
        self.assertEqual(cny_car.price_rub, Decimal("600000"))
        self.assertEqual(fixed.price_rub, Decimal("999000"))

    def test_parse_cbr_xml_cny(self):
        xml = """<?xml version="1.0" encoding="windows-1251"?>
        <ValCurs Date="10.09.2026" name="Foreign Currency Market">
            <Valute ID="R01375">
                <NumCode>156</NumCode>
                <CharCode>CNY</CharCode>
                <Nominal>1</Nominal>
                <Name>Yuan</Name>
                <Value>12,8849</Value>
                <VunitRate>12,8849</VunitRate>
            </Valute>
        </ValCurs>
        """
        with patch("catalog.cbr.fetch_url_text", return_value=xml):
            self.assertEqual(fetch_cbr_cny_rate(), Decimal("12.8849"))

    def test_parse_cbr_xml_respects_nominal(self):
        xml = """<?xml version="1.0"?>
        <ValCurs>
            <Valute>
                <CharCode>CNY</CharCode>
                <Nominal>10</Nominal>
                <Value>128,849</Value>
            </Valute>
        </ValCurs>
        """
        with patch("catalog.cbr.fetch_url_text", return_value=xml):
            self.assertEqual(fetch_cbr_cny_rate(), Decimal("12.8849"))

    def test_cbr_fetch_error_keeps_message(self):
        with patch("catalog.cbr.fetch_url_text", side_effect=RuntimeError("timeout")):
            with self.assertRaises(CbrRateError):
                fetch_cbr_cny_rate()
