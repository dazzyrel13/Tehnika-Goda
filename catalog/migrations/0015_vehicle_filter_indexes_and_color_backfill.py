from django.db import migrations, models


def backfill_color_from_specs(apps, schema_editor):
    Vehicle = apps.get_model("catalog", "Vehicle")
    to_update = []
    for vehicle in Vehicle.objects.all().iterator(chunk_size=200):
        if (vehicle.color or "").strip():
            continue
        specs = vehicle.specs or {}
        if not isinstance(specs, dict):
            continue
        specs_color = str(specs.get("color") or "").strip()
        if not specs_color:
            continue
        vehicle.color = specs_color[:60]
        to_update.append(vehicle)
        if len(to_update) >= 200:
            Vehicle.objects.bulk_update(to_update, ["color"])
            to_update = []
    if to_update:
        Vehicle.objects.bulk_update(to_update, ["color"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0014_vehicle_price_rub_labels"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="color",
            field=models.CharField(
                blank=True, db_index=True, max_length=60, verbose_name="Цвет"
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "year"], name="catalog_veh_pub_year_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "price_rub"], name="catalog_veh_pub_price_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "brand"], name="catalog_veh_pub_brand_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "color"], name="catalog_veh_pub_color_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "is_featured", "-created_at"],
                name="catalog_veh_pub_feat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "mileage"], name="catalog_veh_pub_mile_idx"
            ),
        ),
        migrations.RunPython(backfill_color_from_specs, noop_reverse),
    ]
