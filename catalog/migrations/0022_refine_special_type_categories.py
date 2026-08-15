from django.db import migrations

KEEP_SPECIAL_TYPES = (
    ("special_lifts", "Автовышки"),
    ("special_cranes", "Башенные краны"),
)

RETIRE_SPECIAL_SLUGS = (
    "special_frontal",
    "special_forklift",
    "special_excavators",
)


def _ensure_children(Category, parent, children):
    for slug, name in children:
        obj, created = Category.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "parent": parent},
        )
        if not created:
            fields = []
            if obj.parent_id != parent.pk:
                obj.parent = parent
                fields.append("parent")
            if obj.name != name:
                obj.name = name
                fields.append("name")
            if fields:
                obj.save(update_fields=fields)


def refine_special_types(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Vehicle = apps.get_model("catalog", "Vehicle")

    special, _ = Category.objects.get_or_create(
        slug="special",
        defaults={"name": "Спецтехника"},
    )
    _ensure_children(Category, special, KEEP_SPECIAL_TYPES)

    retired = list(Category.objects.filter(slug__in=RETIRE_SPECIAL_SLUGS))
    if retired:
        retired_ids = [cat.pk for cat in retired]
        Vehicle.objects.filter(category_id__in=retired_ids).update(category=special)
        Category.objects.filter(pk__in=retired_ids).delete()

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
        ("catalog", "0021_vehicle_unpublished_by_default"),
    ]

    operations = [
        migrations.RunPython(refine_special_types, noop),
    ]
