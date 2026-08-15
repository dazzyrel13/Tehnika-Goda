from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0020_delete_dealeroffer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="is_published",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Новые и импортированные объявления скрыты, пока не включите.",
                verbose_name="Опубликовано",
            ),
        ),
    ]
