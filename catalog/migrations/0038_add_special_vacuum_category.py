from django.db import migrations

CATEGORY = ("special_vacuum", "Ассенизаторы")


def add_assenizators(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")

    special, _ = Category.objects.get_or_create(
        slug="special",
        defaults={"name": "Спецтехника"},
    )
    obj, created = Category.objects.get_or_create(
        slug=CATEGORY[0],
        defaults={"name": CATEGORY[1], "parent": special},
    )
    if not created:
        fields = []
        if obj.parent_id != special.pk:
            obj.parent = special
            fields.append("parent")
        if obj.name != CATEGORY[1]:
            obj.name = CATEGORY[1]
            fields.append("name")
        if fields:
            obj.save(update_fields=fields)

    try:
        from catalog.cache_helpers import invalidate_nav_cache, invalidate_subtree_cache

        invalidate_nav_cache()
        invalidate_subtree_cache()
    except Exception:
        pass


def remove_assenizators(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Vehicle = apps.get_model("catalog", "Vehicle")
    special = Category.objects.filter(slug="special").first()
    cat = Category.objects.filter(slug=CATEGORY[0]).first()
    if not cat:
        return
    if special:
        Vehicle.objects.filter(category_id=cat.pk).update(category=special)
    cat.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0037_vehicle_rutube_url"),
    ]

    operations = [
        migrations.RunPython(add_assenizators, remove_assenizators),
    ]
