from django.db import migrations
from django.utils.text import slugify
from unidecode import unidecode

from catalog.china_brands import CHINA_CAR_BRANDS


def seed_china_brands(apps, schema_editor):
    Brand = apps.get_model("catalog", "Brand")
    for name in CHINA_CAR_BRANDS:
        slug = slugify(unidecode(name)) or "brand"
        brand, created = Brand.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "seo_landing_enabled": True},
        )
        if not created and not brand.seo_landing_enabled:
            brand.seo_landing_enabled = True
            brand.save(update_fields=["seo_landing_enabled"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0028_carmodel_seo_landing"),
    ]

    operations = [
        migrations.RunPython(seed_china_brands, noop),
    ]
