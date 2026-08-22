"""Tests for China brand directory seed list."""

from django.test import SimpleTestCase

from catalog.china_brands import CHINA_CAR_BRANDS


class ChinaBrandsListTests(SimpleTestCase):
    def test_list_is_substantial_and_unique(self):
        self.assertGreaterEqual(len(CHINA_CAR_BRANDS), 70)
        self.assertEqual(len(CHINA_CAR_BRANDS), len(set(CHINA_CAR_BRANDS)))

    def test_includes_major_brands(self):
        for name in ("BYD", "Zeekr", "Toyota", "Volkswagen", "Li Auto", "NIO"):
            self.assertIn(name, CHINA_CAR_BRANDS)
