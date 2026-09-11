from decimal import Decimal

from django.db import migrations


def seed_platform_ratings(apps, schema_editor):
    ReviewPlatformSettings = apps.get_model("content", "ReviewPlatformSettings")
    obj, _ = ReviewPlatformSettings.objects.get_or_create(pk=1)
    obj.yandex_rating = Decimal("5.0")
    obj.yandex_count = 7
    obj.twogis_rating = Decimal("5.0")
    obj.twogis_count = 7
    obj.save()


def clear_platform_ratings(apps, schema_editor):
    ReviewPlatformSettings = apps.get_model("content", "ReviewPlatformSettings")
    ReviewPlatformSettings.objects.filter(pk=1).update(
        yandex_rating=None,
        yandex_count=None,
        twogis_rating=None,
        twogis_count=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0014_review_platform_ratings"),
    ]

    operations = [
        migrations.RunPython(seed_platform_ratings, clear_platform_ratings),
    ]
