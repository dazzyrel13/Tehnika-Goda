from django.db import migrations





def ensure_categories(apps, schema_editor):

    Category = apps.get_model("catalog", "Category")

    cars, _ = Category.objects.get_or_create(

        slug="cars",

        defaults={"name": "Легковые автомобили"},

    )

    children = [

        ("cars_new", "Новые"),

        ("cars_used", "С пробегом"),

        ("cars_bought", "Выкупленные"),

        ("cars_sedan", "Седаны"),

        ("cars_crossover", "Кроссоверы"),

        ("cars_suv", "Внедорожники"),

        ("cars_minivan", "Минивэны"),

    ]

    for slug, name in children:

        obj, created = Category.objects.get_or_create(

            slug=slug,

            defaults={"name": name, "parent": cars},

        )

        if not created and obj.parent_id is None:

            obj.parent = cars

            obj.name = obj.name or name

            obj.save(update_fields=["parent", "name"])



    # Legacy orphan "sedan" → under cars as cars_sedan if free

    orphan = Category.objects.filter(slug="sedan", parent__isnull=True).first()

    if orphan and not Category.objects.filter(slug="cars_sedan").exclude(pk=orphan.pk).exists():

        orphan.slug = "cars_sedan"

        orphan.name = "Седаны"

        orphan.parent = cars

        orphan.save(update_fields=["slug", "name", "parent"])

    elif orphan:

        orphan.parent = cars

        orphan.save(update_fields=["parent"])





def noop(apps, schema_editor):

    pass





class Migration(migrations.Migration):

    dependencies = [

        ("catalog", "0017_vehicle_featured_bought_label"),

    ]



    operations = [

        migrations.RunPython(ensure_categories, noop),

    ]


