from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations


def seed_promo_banners(apps, schema_editor):
    PromoBanner = apps.get_model("content", "PromoBanner")
    if PromoBanner.objects.exists():
        return

    from content.models import PromoBanner as LivePromoBanner

    seeds = (
        {
            "file": "credit.png",
            "title": "Авто в кредит",
            "teaser": "Выгодные условия и быстрое одобрение. Автомобили под заказ из Китая.",
            "sort_order": 10,
        },
        {
            "file": "winter-tires.jpg",
            "title": "Зимние шины в подарок",
            "teaser": "При заказе авто до 30 сентября — комплект зимней резины бесплатно.",
            "sort_order": 20,
        },
    )
    base = Path(settings.BASE_DIR) / "data" / "promos"
    for seed in seeds:
        path = base / seed["file"]
        if not path.exists():
            continue
        banner = LivePromoBanner(
            title=seed["title"],
            teaser=seed["teaser"],
            link_url="#leads-section",
            is_published=True,
            sort_order=seed["sort_order"],
        )
        with path.open("rb") as fh:
            banner.image.save(path.name, File(fh), save=False)
        banner.save()


def unseed_promo_banners(apps, schema_editor):
    PromoBanner = apps.get_model("content", "PromoBanner")
    PromoBanner.objects.filter(
        title__in=("Авто в кредит", "Зимние шины в подарок")
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0009_promobanner"),
    ]

    operations = [
        migrations.RunPython(seed_promo_banners, unseed_promo_banners),
    ]
