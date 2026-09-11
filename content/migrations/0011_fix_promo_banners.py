from django.db import migrations


def fix_promo_banners(apps, schema_editor):
    from content.promos import resync_default_promos

    resync_default_promos(replace_all=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0010_seed_promo_banners"),
    ]

    operations = [
        migrations.RunPython(fix_promo_banners, noop),
    ]
