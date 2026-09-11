from pathlib import Path

from django.conf import settings
from django.db import migrations


def load_price_list(apps, schema_editor):
    PriceListItem = apps.get_model("catalog", "PriceListItem")
    if PriceListItem.objects.exists():
        return
    path = Path(settings.BASE_DIR) / "data" / "avto_pod_zakaz_price.xlsx"
    if not path.exists():
        return
    from catalog.price_list import import_price_list

    import_price_list(path, replace=True)


def noop_reverse(apps, schema_editor):
    PriceListItem = apps.get_model("catalog", "PriceListItem")
    PriceListItem.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0035_pricelistitem"),
    ]

    operations = [
        migrations.RunPython(load_price_list, noop_reverse),
    ]
