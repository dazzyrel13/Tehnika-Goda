from django.db import migrations, models


def backfill_published_on_home(apps, schema_editor):
    Vehicle = apps.get_model("catalog", "Vehicle")
    Vehicle.objects.filter(is_published=True).update(show_on_home=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0023_vehicle_cny_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="show_on_home",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Показывать блок на главной. В каталоге видно при включённом «Опубликовано».",
                verbose_name="На главной",
            ),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["is_published", "show_on_home", "-created_at"],
                name="catalog_veh_pub_home_idx",
            ),
        ),
        migrations.RunPython(backfill_published_on_home, noop),
    ]
