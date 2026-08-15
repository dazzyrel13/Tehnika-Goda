from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0005_review_source_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="city",
            field=models.CharField(
                blank=True, max_length=100, verbose_name="Город клиента"
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="Прямая ссылка на отзыв. Если пусто — берётся ссылка площадки из настроек.",
                verbose_name="Ссылка на отзыв",
            ),
        ),
    ]
