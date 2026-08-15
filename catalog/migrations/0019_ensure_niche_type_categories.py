from django.db import migrations


TRUCK_TYPES = (
    ("trucks_trucks", "Грузовики"),
    ("trucks_vans", "Фургоны"),
    ("trucks_km", "Бортовые с КМУ"),
    ("trucks_evac", "Эвакуаторы"),
)

SPECIAL_TYPES = (
    ("special_lifts", "Автовышки"),
    ("special_frontal", "Фронтальные погрузчики"),
    ("special_forklift", "Вилочные погрузчики"),
    ("special_excavators", "Экскаваторы-погрузчики"),
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
            if not obj.name:
                obj.name = name
                fields.append("name")
            if fields:
                obj.save(update_fields=fields)


def ensure_niche_types(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Vehicle = apps.get_model("catalog", "Vehicle")

    trucks, _ = Category.objects.get_or_create(
        slug="trucks",
        defaults={"name": "Коммерческий транспорт"},
    )
    special, _ = Category.objects.get_or_create(
        slug="special",
        defaults={"name": "Спецтехника"},
    )
    cars, _ = Category.objects.get_or_create(
        slug="cars",
        defaults={"name": "Легковые автомобили"},
    )

    _ensure_children(Category, trucks, TRUCK_TYPES)
    _ensure_children(Category, special, SPECIAL_TYPES)

    # Drop duplicate "Седан" if "Седаны" already exists under cars
    sedan = Category.objects.filter(slug="sedan").first()
    cars_sedan = Category.objects.filter(slug="cars_sedan").first()
    if sedan and cars_sedan and sedan.pk != cars_sedan.pk:
        Vehicle.objects.filter(category=sedan).update(category=cars_sedan)
        sedan.delete()
    elif sedan and not cars_sedan:
        sedan.slug = "cars_sedan"
        sedan.name = "Седаны"
        sedan.parent = cars
        sedan.save(update_fields=["slug", "name", "parent"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0018_ensure_car_filter_categories"),
    ]

    operations = [
        migrations.RunPython(ensure_niche_types, noop),
    ]
