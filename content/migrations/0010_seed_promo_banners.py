from django.db import migrations


def seed_promo_banners(apps, schema_editor):
    PromoBanner = apps.get_model("content", "PromoBanner")
    if PromoBanner.objects.exists():
        return
    from content.promos import resync_default_promos

    resync_default_promos(replace_all=False)


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
