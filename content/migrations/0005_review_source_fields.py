from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0004_alter_review_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="source",
            field=models.CharField(
                choices=[
                    ("2gis", "2ГИС"),
                    ("avito", "Авито"),
                    ("yandex", "Яндекс Карты"),
                ],
                db_index=True,
                default="yandex",
                max_length=20,
                verbose_name="Источник",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="Прямая ссылка на отзыв в 2ГИС, Авито или Яндекс Картах",
                verbose_name="Ссылка на отзыв",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="order",
            field=models.PositiveIntegerField(default=0, verbose_name="Порядок вывода"),
        ),
        migrations.AlterField(
            model_name="review",
            name="date",
            field=models.DateField(
                default=django.utils.timezone.localdate,
                verbose_name="Дата отзыва",
            ),
        ),
        migrations.AlterModelOptions(
            name="review",
            options={
                "ordering": ["order", "-date"],
                "verbose_name": "Отзыв клиента",
                "verbose_name_plural": "Отзывы клиентов",
            },
        ),
    ]
