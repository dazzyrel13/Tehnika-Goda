from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0019_ensure_niche_type_categories"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DealerOffer",
        ),
    ]
