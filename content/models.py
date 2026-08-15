from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ReviewPlatformSettings(models.Model):
    """
    Singleton: общие ссылки на профили компании на площадках отзывов.
    Редактируется в админке — «Ссылки на отзывы».
    """

    yandex_url = models.URLField(
        "Ссылка на Яндекс Карты",
        blank=True,
        help_text="Профиль или карточка организации в Яндекс Картах",
    )
    twogis_url = models.URLField(
        "Ссылка на 2ГИС",
        blank=True,
        help_text="Карточка организации в 2ГИС",
    )
    avito_url = models.URLField(
        "Ссылка на Авито",
        blank=True,
        help_text="Профиль продавца или отзывы на Авито",
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Ссылки на отзывы"
        verbose_name_plural = "Ссылки на отзывы"

    def __str__(self):
        return "Ссылки на Яндекс / 2ГИС / Авито"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete("catalog:review_platforms")

    def delete(self, *args, **kwargs):
        # Prevent deleting the singleton row.
        return

    @classmethod
    def load(cls) -> "ReviewPlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def url_for_source(self, source: str) -> str:
        mapping = {
            "yandex": self.yandex_url,
            "2gis": self.twogis_url,
            "avito": self.avito_url,
        }
        return (mapping.get(source) or "").strip()


class Review(models.Model):
    SOURCE_2GIS = "2gis"
    SOURCE_AVITO = "avito"
    SOURCE_YANDEX = "yandex"
    SOURCE_CHOICES = [
        (SOURCE_2GIS, "2ГИС"),
        (SOURCE_AVITO, "Авито"),
        (SOURCE_YANDEX, "Яндекс Карты"),
    ]

    client_name = models.CharField("Имя клиента", max_length=100)
    city = models.CharField("Город клиента", max_length=100, blank=True)
    vehicle_purchased = models.CharField("Купленное авто", max_length=200, blank=True)
    comment = models.TextField("Комментарий/Отзыв")
    rating = models.PositiveIntegerField(
        "Рейтинг (1-5)",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    source = models.CharField(
        "Источник",
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_YANDEX,
        db_index=True,
    )
    source_url = models.URLField(
        "Ссылка на отзыв",
        blank=True,
        help_text="Прямая ссылка на этот отзыв. Если пусто — берётся общая ссылка площадки.",
    )
    is_published = models.BooleanField("Опубликовано", default=True)
    date = models.DateField("Дата отзыва", default=timezone.localdate)
    order = models.PositiveIntegerField("Порядок вывода", default=0)

    class Meta:
        verbose_name = "Отзыв клиента"
        verbose_name_plural = "Отзывы клиентов"
        ordering = ["order", "-date"]

    def __str__(self):
        return f"Отзыв от {self.client_name}"

    @property
    def source_label(self) -> str:
        return dict(self.SOURCE_CHOICES).get(self.source, self.source)

    @property
    def source_link_label(self) -> str:
        labels = {
            self.SOURCE_2GIS: "Отзыв на 2ГИС",
            self.SOURCE_AVITO: "Отзыв на Авито",
            self.SOURCE_YANDEX: "Отзыв на Яндекс Картах",
        }
        return labels.get(self.source, f"Отзыв на {self.source_label}")

    @property
    def initials(self) -> str:
        parts = [p for p in self.client_name.replace(".", " ").split() if p]
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        if parts:
            return parts[0][:2].upper()
        return "?"

    @property
    def subtitle(self) -> str:
        bits = [b for b in (self.city, self.vehicle_purchased) if b]
        return " · ".join(bits)

    @property
    def avatar_tone(self) -> int:
        return (self.pk or 0) % 4

    def source_icon(self) -> str:
        return {
            self.SOURCE_2GIS: "images/brands/2gis.png",
            self.SOURCE_AVITO: "images/brands/avito.png",
            self.SOURCE_YANDEX: "images/brands/yandex-maps.png",
        }.get(self.source, "images/brands/yandex-maps.png")

    def resolved_source_url(self) -> str:
        if self.source_url:
            return self.source_url
        return platform_url_for_source(self.source)


def platform_url_for_source(source: str) -> str:
    """Admin settings first, then optional .env fallback."""
    try:
        settings_obj = ReviewPlatformSettings.load()
        url = settings_obj.url_for_source(source)
        if url:
            return url
    except Exception:
        pass

    from django.conf import settings

    return {
        Review.SOURCE_2GIS: getattr(settings, "REVIEW_2GIS_URL", ""),
        Review.SOURCE_AVITO: getattr(settings, "REVIEW_AVITO_URL", ""),
        Review.SOURCE_YANDEX: getattr(settings, "REVIEW_YANDEX_URL", ""),
    }.get(source, "")
