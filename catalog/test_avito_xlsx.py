from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from openpyxl import Workbook

from catalog.avito_xlsx import (
    import_avito_xlsx,
    normalize_text,
    parse_avito_xlsx,
)
from catalog.models import Brand, Category, Vehicle


def _build_avito_xlsx(rows: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Автомобили-С пробегом"
    ws.append(["Транспорт - Автомобили - С пробегом"])
    headers = [
        "Id",
        "AvitoId",
        "Make",
        "Model",
        "Year",
        "Kilometrage",
        "Color",
        "Title",
        "Price",
        "Description",
        "BodyType",
        "Transmission",
        "FuelType",
        "Power",
        "ImageUrls",
        "VIN",
    ]
    ws.append(headers)
    ws.append(["Обязательный"] * len(headers))
    ws.append(["Подробнее"] * len(headers))
    ws.append([None] * len(headers))
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class AvitoXlsxImportTests(TestCase):
    def setUp(self):
        self.brand, _ = Brand.objects.get_or_create(
            slug="audi", defaults={"name": "Audi"}
        )
        self.category, _ = Category.objects.get_or_create(
            slug="cars_sedan", defaults={"name": "Седаны"}
        )

    def test_normalize_text(self):
        self.assertEqual(
            normalize_text("Audi\u00a0A3, 2021!"),
            "audi a3 2021",
        )

    def test_parse_avito_xlsx(self):
        buf = _build_avito_xlsx(
            [
                {
                    "Id": "111",
                    "AvitoId": "8207042398",
                    "Make": "Audi",
                    "Model": "A3",
                    "Year": "2021",
                    "Kilometrage": "37000",
                    "Color": "Белый",
                    "Title": "Audi A3 1.4 AT, 2021, 37 000 км",
                    "Price": "1820000",
                    "Description": "<p>Test</p>",
                    "BodyType": "Седан",
                    "Transmission": "Автомат",
                    "FuelType": "Бензин",
                    "Power": "150",
                    "ImageUrls": "https://example.com/a.jpg | https://example.com/b.jpg",
                    "VIN": "LFV2A28Y5M6659246",
                }
            ]
        )
        listings = parse_avito_xlsx(buf)
        self.assertEqual(len(listings), 1)
        item = listings[0]
        self.assertEqual(item.avito_id, 8207042398)
        self.assertEqual(item.make, "Audi")
        self.assertEqual(item.mileage, 37000)
        self.assertEqual(item.price_rub, Decimal("1820000"))
        self.assertEqual(len(item.image_urls), 2)
        self.assertEqual(item.specs.get("vin"), "LFV2A28Y5M6659246")

    def test_skip_by_avito_id(self):
        Vehicle.objects.create(
            title="Audi A3",
            brand=self.brand,
            category=self.category,
            year=2021,
            mileage=100,
            color="Чёрный",
            price_rub=1,
            avito_item_id=8207042398,
            slug="audi-a3-existing",
        )
        buf = _build_avito_xlsx(
            [
                {
                    "AvitoId": "8207042398",
                    "Make": "Audi",
                    "Model": "A3",
                    "Year": "2021",
                    "Kilometrage": "37000",
                    "Color": "Белый",
                    "Title": "Audi A3",
                    "Price": "1820000",
                    "BodyType": "Седан",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=False, download_photos=False)
        self.assertEqual(report.created, 0)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_skip_by_title_year_mileage_color(self):
        Vehicle.objects.create(
            title="Audi A3",
            brand=self.brand,
            category=self.category,
            model="A3",
            year=2021,
            mileage=37000,
            color="Белый",
            price_rub=1,
            slug="audi-a3-fp",
        )
        buf = _build_avito_xlsx(
            [
                {
                    "AvitoId": "999888777",
                    "Make": "Audi",
                    "Model": "A3",
                    "Year": "2021",
                    "Kilometrage": "37000",
                    "Color": "Белый",
                    "Title": "Audi A3 1.4 AT, 2021, 37 000 км",
                    "Price": "1820000",
                    "BodyType": "Седан",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=False, download_photos=False)
        self.assertEqual(report.created, 0)
        self.assertEqual(report.skipped, 1)
        self.assertIn("название/год/пробег/цвет", report.skipped_reasons[0])

    @patch("catalog.avito_xlsx._download_images", return_value=([], []))
    def test_creates_unpublished_draft(self, _mock_photos):
        buf = _build_avito_xlsx(
            [
                {
                    "AvitoId": "555444333",
                    "Make": "Volkswagen",
                    "Model": "Lavida",
                    "Year": "2023",
                    "Kilometrage": "17135",
                    "Color": "Белый",
                    "Title": "Volkswagen Lavida 1.4 AMT, 2023",
                    "Price": "1505000",
                    "Description": "<p>Ok</p><script>alert(1)</script>",
                    "BodyType": "Седан",
                    "Transmission": "Робот",
                    "FuelType": "Бензин",
                    "Power": "150",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=False, download_photos=True)
        self.assertEqual(report.created, 1)
        self.assertEqual(report.skipped, 0)
        vehicle = Vehicle.objects.get(pk=report.created_ids[0])
        self.assertFalse(vehicle.is_published)
        self.assertEqual(vehicle.avito_item_id, 555444333)
        self.assertEqual(vehicle.title, "Volkswagen Lavida")
        self.assertEqual(vehicle.price_rub, Decimal("1505000"))
        self.assertIsNone(vehicle.price_cny)
        self.assertNotIn("<script>", vehicle.description)

    def test_dry_run_does_not_create(self):
        buf = _build_avito_xlsx(
            [
                {
                    "AvitoId": "111222333",
                    "Make": "Nissan",
                    "Model": "Qashqai",
                    "Year": "2022",
                    "Kilometrage": "10000",
                    "Color": "Серый",
                    "Price": "2000000",
                    "BodyType": "Кроссовер",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=True, download_photos=False)
        self.assertEqual(report.created, 1)
        self.assertEqual(Vehicle.objects.count(), 0)
