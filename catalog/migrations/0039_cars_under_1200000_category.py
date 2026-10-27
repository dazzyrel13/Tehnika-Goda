from django.db import migrations


def ensure_price_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    cars, _ = Category.objects.get_or_create(
        slug="cars",
        defaults={"name": "Легковые автомобили"},
    )
    category, created = Category.objects.get_or_create(
        slug="cars_under_1200000",
        defaults={
            "name": "Автомобили до 1 200 000 ₽",
            "parent": cars,
        },
    )
    if not created:
        fields = []
        if category.parent_id != cars.pk:
            category.parent = cars
            fields.append("parent")
        if category.name != "Автомобили до 1 200 000 ₽":
            category.name = "Автомобили до 1 200 000 ₽"
            fields.append("name")
        if fields:
            category.save(update_fields=fields)

    try:
        from catalog.cache_helpers import invalidate_nav_cache, invalidate_subtree_cache

        invalidate_nav_cache()
        invalidate_subtree_cache()
    except Exception:
        pass


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0038_add_special_vacuum_category"),
    ]

    operations = [
        migrations.RunPython(ensure_price_category, noop),
    ]