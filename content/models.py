import uuid

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
        max_length=500,
        help_text="Профиль или карточка организации в Яндекс Картах",
    )
    twogis_url = models.URLField(
        "Ссылка на 2ГИС",
        blank=True,
        max_length=500,
        help_text="Карточка организации в 2ГИС",
    )
    avito_url = models.URLField(
        "Ссылка на Авито",
        blank=True,
        max_length=500,
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
        from catalog.cache_helpers import invalidate_home_reviews_cache

        invalidate_home_reviews_cache()

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
        max_length=500,
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


def promo_banner_path(instance, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] or "webp").lower()
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        ext = "webp"
    return f"promos/{timezone.now():%Y/%m}/{uuid.uuid4().hex[:12]}.{ext}"


class PromoBanner(models.Model):
    """Баннер акции на главной: картинка + короткий текст."""

    title = models.CharField("Заголовок", max_length=120)
    teaser = models.CharField(
        "Короткий текст",
        max_length=180,
        help_text="1–2 строки под баннером на главной.",
    )
    image = models.ImageField("Баннер", upload_to=promo_banner_path)
    link_url = models.CharField(
        "Ссылка",
        max_length=300,
        blank=True,
        default="#leads-section",
        help_text="Куда ведёт клик. Например #leads-section или /avto-pod-zakaz/.",
    )
    is_published = models.BooleanField("Опубликовано", default=True, db_index=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["sort_order", "-updated_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        from utils.image_processing import process_image_to_webp, should_process_image

        update_fields = kwargs.get("update_fields")
        touch_image = update_fields is None or "image" in update_fields
        if touch_image and self.image and should_process_image(self.image):
            processed = process_image_to_webp(self.image, quality=85, max_width=1200)
            if processed:
                self.image = processed
        super().save(*args, **kwargs)
        try:
            cache.delete("content:home_promos")
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        try:
            cache.delete("content:home_promos")
        except Exception:
            pass
        super().delete(*args, **kwargs)

    @property
    def href(self) -> str:
        return (self.link_url or "").strip() or "#leads-section"
