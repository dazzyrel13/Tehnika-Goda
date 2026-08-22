from django.db import migrations, models


def sync_is_new_from_category(apps, schema_editor):
    Vehicle = apps.get_model("catalog", "Vehicle")
    Vehicle.objects.filter(category__slug="cars_new").update(is_new=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0026_show_on_home_default_true"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="is_new",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Плашка «Новые» и фильтр «Новые» (пробег 0–3 тыс. км ок).",
                verbose_name="Новые",
            ),
        ),
        migrations.RunPython(sync_is_new_from_category, noop),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "is_new", "-created_at"],
                name="catalog_veh_pub_new_idx",
            ),
        ),
    ]
