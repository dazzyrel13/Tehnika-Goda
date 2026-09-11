from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, PriceListItem
from catalog.price_list import extract_brand, import_price_list, parse_price_list


class PriceListParseTests(TestCase):
    def test_extract_brand_aliases(self):
        self.assertEqual(extract_brand("BMW X1"), "BMW")
        self.assertEqual(extract_brand("AUDI A3L"), "Audi")
        self.assertEqual(extract_brand("Mercedes-Benz A180"), "Mercedes-Benz")
        self.assertEqual(extract_brand("MG5 400"), "MG")
        self.assertEqual(extract_brand("GAC Trumpchi M6"), "GAC")

    def test_parse_dedupes_min_price(self):
        from openpyxl import Workbook
        from pathlib import Path
        import tempfile

        wb = Workbook()
        ws = wb.active
        ws.append(["Категория", "Название", "Идентификатор", "Описание", "Короткое описание", "Цена"])
        ws.append(["Автомобили", "BMW X1", "", "", "", 2_500_000])
        ws.append(["Автомобили", "BMW X1", "", "", "", 2_200_000])
        ws.append(["Автомобили", "Toyota Levin", "", "", "", 1_500_000])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "price.xlsx"
            wb.save(path)
            rows = parse_price_list(path)
        self.assertEqual(len(rows), 2)
        bmw = next(r for r in rows if r.title == "BMW X1")
        self.assertEqual(bmw.price_rub, 2_200_000)
        self.assertEqual(bmw.brand, "BMW")

    def test_import_creates_rows_and_brand_slug(self):
        Brand.objects.get_or_create(name="BMW", defaults={"slug": "bmw"})
        from openpyxl import Workbook
        from pathlib import Path
        import tempfile

        wb = Workbook()
        ws = wb.active
        ws.append(["Категория", "Название", "x", "y", "z", "Цена"])
        ws.append(["Автомобили", "BMW X1 (2023)", "", "", "", 2_963_560])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "price.xlsx"
            wb.save(path)
            report = import_price_list(path, replace=True)
        self.assertEqual(report.created + report.updated, 1)
        item = PriceListItem.objects.get(title="BMW X1 (2023)")
        self.assertEqual(item.brand, "BMW")
        self.assertEqual(item.brand_slug, "bmw")
        self.assertEqual(item.price_rub, 2_963_560)


class AvtoPodZakazPageTests(TestCase):
    def test_page_renders_groups_and_seo(self):
        PriceListItem.objects.update_or_create(
            title="BMW X1 Test SEO",
            defaults={
                "brand": "BMW",
                "brand_slug": "",
                "price_rub": 2_255_560,
                "sort_order": 0,
                "is_active": True,
            },
        )
        PriceListItem.objects.update_or_create(
            title="Haval Jolion Test SEO",
            defaults={
                "brand": "Haval",
                "price_rub": 1_429_560,
                "sort_order": 10,
                "is_active": True,
            },
        )
        response = self.client.get(reverse("avto_pod_zakaz"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Авто из Китая. Прайс")
        self.assertContains(response, "BMW из Китая")
        self.assertContains(response, "BMW X1 Test SEO")
        self.assertContains(response, "Из Китая")
        self.assertContains(response, "FAQPage")
        self.assertContains(response, 'id="bmw"')
