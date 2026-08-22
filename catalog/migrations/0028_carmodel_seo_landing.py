# Generated manually for SEO model landing pages.

from django.db import migrations, models
from django.utils.text import slugify
from unidecode import unidecode


def _unique_model_slug(brand_id, name, seen):
    base = slugify(unidecode(name)) or "model"
    slug = base
    key = (brand_id, slug)
    n = 2
    while key in seen:
        slug = f"{base}-{n}"
        key = (brand_id, slug)
        n += 1
    seen.add(key)
    return slug


def bootstrap_seo_data(apps, schema_editor):
    Brand = apps.get_model("catalog", "Brand")
    CarModel = apps.get_model("catalog", "CarModel")
    Vehicle = apps.get_model("catalog", "Vehicle")

    brand_ids_with_stock = set(
        Vehicle.objects.filter(is_published=True).values_list("brand_id", flat=True)
    )
    Brand.objects.filter(pk__in=brand_ids_with_stock).update(seo_landing_enabled=True)

    seen = set(
        (row["brand_id"], row["slug"])
        for row in CarModel.objects.values("brand_id", "slug")
    )
    for row in (
        Vehicle.objects.filter(is_published=True)
        .exclude(model="")
        .values("brand_id", "model")
        .distinct()
    ):
        name = (row["model"] or "").strip()
        if not name:
            continue
        brand_id = row["brand_id"]
        slug = _unique_model_slug(brand_id, name, seen)
        CarModel.objects.get_or_create(
            brand_id=brand_id,
            slug=slug,
            defaults={"name": name, "is_published": True},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0027_vehicle_is_new"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="seo_landing_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Отдельная страница «Марка из Китая» в каталоге и в списке марок, "
                    "даже если сейчас нет объявлений."
                ),
                verbose_name="SEO-страница марки",
            ),
        ),
        migrations.CreateModel(
            name="CarModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Например: 001, L6, 300",
                        max_length=100,
                        verbose_name="Модель",
                    ),
                ),
                ("slug", models.SlugField(blank=True, max_length=120)),
                (
                    "intro",
                    models.TextField(
                        blank=True,
                        help_text="Если пусто — подставится стандартный текст на странице модели.",
                        verbose_name="SEO-текст (необязательно)",
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(
                        db_index=True, default=True, verbose_name="Опубликовано"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveIntegerField(default=0, verbose_name="Порядок"),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "brand",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="car_models",
                        to="catalog.brand",
                        verbose_name="Марка",
                    ),
                ),
            ],
            options={
                "verbose_name": "Модель (SEO)",
                "verbose_name_plural": "Модели (SEO)",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="carmodel",
            constraint=models.UniqueConstraint(
                fields=("brand", "slug"),
                name="catalog_carmodel_brand_slug_uniq",
            ),
        ),
        migrations.RunPython(bootstrap_seo_data, noop),
    ]
