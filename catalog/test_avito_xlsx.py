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

    def test_link_avito_id_on_fingerprint_match_without_id(self):
        vehicle = Vehicle.objects.create(
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
        self.assertEqual(report.skipped, 0)
        self.assertEqual(report.linked, 1)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.avito_item_id, 999888777)
        self.assertIn("привязан AvitoId", report.linked_reasons[0])

    def test_skip_fingerprint_when_other_avito_id_already_set(self):
        Vehicle.objects.create(
            title="Audi A3",
            brand=self.brand,
            category=self.category,
            model="A3",
            year=2021,
            mileage=37000,
            color="Белый",
            price_rub=1,
            avito_item_id=111000111,
            slug="audi-a3-other-id",
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
        self.assertEqual(report.linked, 0)
        self.assertEqual(report.skipped, 1)
        self.assertIn("другой AvitoId", report.skipped_reasons[0])

    @patch("catalog.avito_xlsx.enqueue_avito_photo_fetch")
    def test_creates_unpublished_draft(self, _mock_enqueue):
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
                    "ImageUrls": "https://avito.ru/autoload/a.jpg | https://avito.ru/autoload/b.jpg",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=False, photo_mode="async")
        self.assertEqual(report.created, 1)
        self.assertEqual(report.skipped, 0)
        self.assertEqual(report.photos_queued, 1)
        vehicle = Vehicle.objects.get(pk=report.created_ids[0])
        self.assertFalse(vehicle.is_published)
        self.assertEqual(vehicle.avito_item_id, 555444333)
        self.assertEqual(vehicle.title, "Volkswagen Lavida")
        self.assertEqual(vehicle.price_rub, Decimal("1505000"))
        self.assertIsNone(vehicle.price_cny)
        self.assertNotIn("<script>", vehicle.description)
        self.assertIn("[Название автомобиля] Volkswagen Lavida", vehicle.description)
        self.assertIn("_avito_image_urls", vehicle.specs)
        _mock_enqueue.assert_called_once_with(vehicle.pk)

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

    def test_build_spec_description_has_bracket_rows(self):
        from catalog.avito_xlsx import AvitoListing, build_spec_description

        listing = AvitoListing(
            row_number=1,
            avito_id=1,
            make="Trumpchi",
            model="M6 Pro",
            title="Trumpchi M6 Pro 2022",
            short_title="Trumpchi M6 Pro",
            year=2022,
            mileage=26000,
            color="Белый",
            price_rub=Decimal("1500000"),
            description="<p><strong>Гарантия 6 месяцев</strong></p><p>Текст</p>",
            body_type="Минивэн",
            transmission="Автомат",
            fuel_type="Бензин",
            horsepower=150,
            specs={"vin": "ABC123"},
        )
        text = build_spec_description(listing)
        self.assertIn("[Название автомобиля] Trumpchi M6 Pro", text)
        self.assertIn("[Пробег] 26 000 километров", text)
        self.assertIn("[Цвет] Белый", text)
        self.assertIn("Гарантия 6 месяцев", text)
        self.assertNotIn("<p>", text)

    @patch("catalog.avito_xlsx._fetch_image_bytes")
    def test_download_images_without_dns_pin(self, mock_fetch):
        from io import BytesIO

        from PIL import Image

        from catalog.avito_xlsx import _download_images

        buf = BytesIO()
        Image.new("RGB", (1, 1), color=(255, 0, 0)).save(buf, format="JPEG")
        mock_fetch.return_value = buf.getvalue()
        uploads, warnings = _download_images(["https://avito.ru/autoload/test"])
        self.assertEqual(len(uploads), 1)
        self.assertEqual(warnings, [])

    def test_enrich_existing_updates_description_and_skips_create(self):
        vehicle = Vehicle.objects.create(
            title="Trumpchi M6 Pro",
            brand=self.brand,
            category=self.category,
            model="M6 Pro",
            year=2022,
            mileage=26000,
            color="Белый",
            price_rub=1,
            avito_item_id=777666555,
            description="<p>Сырое HTML с Авито</p>",
            slug="trumpchi-enrich",
        )
        buf = _build_avito_xlsx(
            [
                {
                    "AvitoId": "777666555",
                    "Make": "Trumpchi",
                    "Model": "M6 Pro",
                    "Year": "2022",
                    "Kilometrage": "26000",
                    "Color": "Белый",
                    "Title": "Trumpchi M6 Pro",
                    "Price": "1500000",
                    "Description": "<p>Маркетинг</p>",
                    "BodyType": "Минивэн",
                    "Transmission": "Автомат",
                    "FuelType": "Бензин",
                    "Power": "150",
                }
            ]
        )
        report = import_avito_xlsx(buf, dry_run=False, photo_mode="off")
        self.assertEqual(report.created, 0)
        self.assertEqual(report.descriptions_updated, 1)
        vehicle.refresh_from_db()
        self.assertIn("[Название автомобиля]", vehicle.description)
        self.assertIn("[Год выпуска] 2022", vehicle.description)

    @patch("catalog.avito_xlsx._attach_listing_photos", return_value=(2, []))
    def test_fetch_avito_photos_for_vehicle(self, mock_attach):
        from catalog.avito_xlsx import (
            AVITO_IMAGE_URLS_KEY,
            fetch_avito_photos_for_vehicle,
            store_avito_image_urls,
        )

        vehicle = Vehicle.objects.create(
            title="Photo Car",
            brand=self.brand,
            category=self.category,
            year=2024,
            mileage=1,
            color="Белый",
            price_rub=1,
            slug="photo-car-fetch",
            specs={},
        )
        store_avito_image_urls(
            vehicle, ["https://avito.ru/autoload/1.jpg", "https://avito.ru/autoload/2.jpg"]
        )
        added = fetch_avito_photos_for_vehicle(vehicle.pk)
        self.assertEqual(added, 2)
        mock_attach.assert_called_once()
        vehicle.refresh_from_db()
        self.assertNotIn(AVITO_IMAGE_URLS_KEY, vehicle.specs or {})
