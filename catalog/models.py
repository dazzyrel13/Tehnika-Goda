import os
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import IntegrityError, models
from django.urls import reverse
from django.utils.text import slugify
from unidecode import unidecode

from utils.html_sanitize import sanitize_html
from utils.image_processing import (
    delete_responsive_variants,
    process_image_to_webp,
    should_process_image,
    write_responsive_variants,
)
from utils.pdf_validate import validate_pdf_upload

# Custom save path for brand logos


def brand_logo_path(instance, filename):
    return f"catalog/brands/{instance.slug}/{filename}"


# Custom save path for vehicle photos


def _short_upload_name(filename: str, *, prefix: str = "") -> str:
    """Keep storage names short so ImageField max_length is never exceeded."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    if ext == ".jpeg":
        ext = ".jpg"
    return f"{prefix}{uuid.uuid4().hex[:10]}{ext}"


def vehicle_photo_path(instance, filename):
    slug = (getattr(instance.vehicle, "slug", None) or "vehicle")[:60]
    return f"catalog/vehicles/{slug}/{_short_upload_name(filename)}"


# Custom save path for main image


def vehicle_main_photo_path(instance, filename):
    slug = (getattr(instance, "slug", None) or "vehicle")[:60]
    return f"catalog/vehicles/{slug}/{_short_upload_name(filename, prefix='main_')}"


VEHICLE_SLUG_MAX_LENGTH = 80


def build_unique_vehicle_slug(title: str, *, pk=None) -> str:
    """Slugify title and keep it short enough for URLs and media paths."""
    raw = slugify(unidecode(title or "")) or "vehicle"
    base = raw[:VEHICLE_SLUG_MAX_LENGTH].rstrip("-") or "vehicle"
    slug = base
    num = 1
    while Vehicle.objects.filter(slug=slug).exclude(pk=pk).exists():
        suffix = f"-{num}"
        slug = f"{base[: VEHICLE_SLUG_MAX_LENGTH - len(suffix)].rstrip('-')}{suffix}"
        num += 1
    return slug


class Category(models.Model):
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    name = models.CharField("Название категории", max_length=100)
    slug = models.SlugField(unique=True, help_text="Для SEO URL", blank=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(unidecode(self.name))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:category", kwargs={"category_slug": self.slug})

    def subtree_ids(self) -> set[int]:
        """This category and all nested descendants (any depth)."""
        from django.core.cache import cache

        gen = cache.get("catalog:subtree_gen") or 0
        cache_key = f"catalog:subtree:{gen}:{self.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return set(cached)

        ids = {self.pk}
        frontier = {self.pk}
        while frontier:
            children = set(
                Category.objects.filter(parent_id__in=frontier).values_list(
                    "pk", flat=True
                )
            )
            frontier = children - ids
            ids |= frontier
        cache.set(cache_key, list(ids), 300)
        return ids


class Brand(models.Model):
    name = models.CharField("Марка", max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField("Логотип", upload_to=brand_logo_path, blank=True)
    seo_landing_enabled = models.BooleanField(
        "В справочнике марок (SEO)",
        default=False,
        help_text=(
            "Показывать на странице «Марки авто» и в sitemap, "
            "даже если сейчас нет объявлений в каталоге."
        ),
    )

    class Meta:
        verbose_name = "Марка"
        verbose_name_plural = "Марки"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(unidecode(self.name))
        # Auto-convert logo to WebP if uploaded
        if self.logo and should_process_image(self.logo):
            processed_logo = process_image_to_webp(
                self.logo, quality=90, max_width=400
            )
            if processed_logo:
                self.logo = processed_logo
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:brand", kwargs={"brand_slug": self.slug})


class CarModel(models.Model):
    """SEO landing for brand + model (with or without stock)."""

    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        verbose_name="Марка",
        related_name="car_models",
    )
    name = models.CharField(
        "Модель",
        max_length=100,
        help_text="Например: 001, L6, 300",
    )
    slug = models.SlugField(max_length=120, blank=True)
    intro = models.TextField(
        "SEO-текст (необязательно)",
        blank=True,
        help_text="Если пусто — подставится стандартный текст на странице модели.",
    )
    is_published = models.BooleanField("Опубликовано", default=True, db_index=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Модель (SEO)"
        verbose_name_plural = "Модели (SEO)"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "slug"],
                name="catalog_carmodel_brand_slug_uniq",
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.brand.name} {self.name}".strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(unidecode(self.name)) or "model"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "catalog:model",
            kwargs={"brand_slug": self.brand.slug, "model_slug": self.slug},
        )


def inspection_report_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"catalog/inspection_reports/{uuid.uuid4()}{ext}"


class InspectionReport(models.Model):
    report_uid = models.CharField("UID отчета", max_length=50, unique=True, blank=True)
    title = models.CharField("Название авто для отчета", max_length=200)
    pdf_file = models.FileField(
        "PDF отчет (полный)",
        upload_to=inspection_report_path,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf"]),
            validate_pdf_upload,
        ],
    )

    # Inspection Details
    dealer_verdict = models.TextField("Вердикт дилера", blank=True)
    is_verified = models.BooleanField("Проверка пройдена", default=True)

    created_at = models.DateTimeField("Дата осмотра", auto_now_add=True)

    class Meta:
        verbose_name = "Цифровой отчет"
        verbose_name_plural = "Цифровые отчеты"

    def __str__(self):
        date_str = self.created_at.strftime("%d.%m.%Y") if self.created_at else "новый"
        return f"Отчет {self.report_uid or self.title} от {date_str}"

    def save(self, *args, **kwargs):
        if not self.report_uid:
            self.report_uid = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)


class CurrencyRateSettings(models.Model):
    """
    Singleton: site-wide CNY rate.

    Manual rate (if set) overrides the last successful CBR fetch.
    """

    manual_cny_rate = models.DecimalField(
        "Ручной курс юаня",
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=(
            "Рублей за 1 юань. Если заполнено — используется вместо ЦБ "
            "(удобно, когда сайт ЦБ недоступен)."
        ),
    )
    cbr_cny_rate = models.DecimalField(
        "Курс ЦБ (CNY)",
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        editable=False,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    cbr_fetched_at = models.DateTimeField(
        "Курс ЦБ обновлён",
        null=True,
        blank=True,
        editable=False,
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Курс юаня"
        verbose_name_plural = "Курс юаня"

    def __str__(self):
        return f"Курс юаня (эффективный {self.effective_rate()})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def load(cls) -> "CurrencyRateSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def effective_rate(self) -> Decimal:
        from .currency import FALLBACK_CNY_RATE

        if self.manual_cny_rate is not None:
            return Decimal(self.manual_cny_rate)
        if self.cbr_cny_rate is not None:
            return Decimal(self.cbr_cny_rate)
        return FALLBACK_CNY_RATE

    def rate_source_label(self) -> str:
        if self.manual_cny_rate is not None:
            return "ручной"
        if self.cbr_cny_rate is not None:
            return "ЦБ РФ"
        return "запасной (12.48)"


class EngineType(models.TextChoices):
    PETROL = "petrol", "Бензин"
    ELECTRIC = "electric", "Электрический"
    HYBRID = "hybrid", "Гибрид"


class Vehicle(models.Model):
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, verbose_name="Марка", related_name="vehicles"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, verbose_name="Категория"
    )

    title = models.CharField(
        "Заголовок объявления", max_length=255, help_text="Например: Zeekr 001 2024 FR"
    )
    model = models.CharField("Модель", max_length=100, blank=True)
    slug = models.SlugField(unique=True, max_length=255, blank=True)

    # Core Specs
    year = models.PositiveIntegerField("Год выпуска", default=0, db_index=True)
    mileage = models.PositiveIntegerField("Пробег (км)", default=0, db_index=True)
    horsepower = models.PositiveIntegerField("Лошадиные силы (л.с.)", null=True, blank=True)
    transmission = models.CharField("Коробка передач", max_length=50, blank=True)
    body_type = models.CharField("Тип кузова", max_length=80, blank=True)
    color = models.CharField("Цвет", max_length=60, blank=True, db_index=True)
    engine_type = models.CharField(
        "Тип двигателя",
        max_length=20,
        blank=True,
        choices=EngineType.choices,
        db_index=True,
        help_text="Бензин, электрический или гибрид — для фильтра на сайте.",
    )

    # Pricing
    price_cny = models.DecimalField(
        "Цена, ¥",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Если указана — рубли считаются автоматически по курсу сайта "
            "(ручной или ЦБ). Оставьте пустым, чтобы зафиксировать только рубли."
        ),
    )
    price_rub = models.DecimalField(
        "Цена, ₽",
        max_digits=15,
        decimal_places=0,
        blank=True,
        null=True,
        help_text=(
            "Цена на сайте. При заполненной цене в юанях пересчитывается сама."
        ),
        db_index=True,
    )
    cny_rate = models.DecimalField(
        "Курс юаня (на карточке)",
        max_digits=8,
        decimal_places=4,
        default=Decimal("12.48"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=(
            "Курс, с которым посчитана цена — показывается под ценой на сайте. "
            "Общий курс задаётся в разделе «Курс юаня»."
        ),
    )
    is_currency_fixed = models.BooleanField(
        "Цена только в рублях",
        default=False,
        help_text="Включается автоматически, если юани не заданы.",
    )

    # Avito price sync (site → Avito)
    avito_item_id = models.BigIntegerField(
        "ID объявления Авито",
        null=True,
        blank=True,
        db_index=True,
        help_text="Числовой ID или ссылка вида https://www.avito.ru/.../1234567890",
    )
    avito_price_synced_at = models.DateTimeField(
        "Цена ушла на Авито",
        null=True,
        blank=True,
    )
    avito_price_sync_error = models.CharField(
        "Ошибка синхронизации Авито",
        max_length=255,
        blank=True,
        default="",
    )

    # Specs & Description
    description = models.TextField("Описание", blank=True)
    specs = models.JSONField(
        "Технические характеристики (ТТХ)",
        default=dict,
        help_text="Например: {'power': '422 л.с.', 'range': '600 км'}",
    )

    # Media
    main_image = models.ImageField(
        "Основное фото",
        upload_to=vehicle_main_photo_path,
        blank=True,
        null=True,
        max_length=255,
    )
    report = models.OneToOneField(
        InspectionReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Цифровой отчет",
    )

    # Status & SEO
    is_published = models.BooleanField(
        "Опубликовано",
        default=False,
        db_index=True,
        help_text="Новые и импортированные объявления скрыты, пока не включите.",
    )
    is_featured = models.BooleanField(
        "Выкупленный",
        default=False,
        db_index=True,
        help_text="Показывать плашку «Выкупленные» и включать в фильтр выкупленных.",
    )
    is_new = models.BooleanField(
        "Новые",
        default=False,
        db_index=True,
        help_text="Плашка «Новые» и фильтр «Новые» (пробег 0–3 тыс. км ок).",
    )
    show_on_home = models.BooleanField(
        "На главной",
        default=True,
        db_index=True,
        help_text="Показывать в блоке на главной (нужно ещё «Опубликовано»). Снимите, если авто только в каталоге.",
    )
    badge_text = models.CharField(
        "Текст на бэйдже",
        max_length=20,
        blank=True,
        help_text="Свой текст плашки (если не «Новые» / «Выкупленные»). Например: В ПУТИ",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["is_published", "year"], name="catalog_veh_pub_year_idx"
            ),
            models.Index(
                fields=["is_published", "price_rub"], name="catalog_veh_pub_price_idx"
            ),
            models.Index(
                fields=["is_published", "brand"], name="catalog_veh_pub_brand_idx"
            ),
            models.Index(
                fields=["is_published", "color"], name="catalog_veh_pub_color_idx"
            ),
            models.Index(
                fields=["is_published", "engine_type"],
                name="catalog_veh_pub_engine_idx",
            ),
            models.Index(
                fields=["is_published", "is_featured", "-created_at"],
                name="catalog_veh_pub_feat_idx",
            ),
            models.Index(
                fields=["is_published", "is_new", "-created_at"],
                name="catalog_veh_pub_new_idx",
            ),
            models.Index(
                fields=["is_published", "mileage"], name="catalog_veh_pub_mile_idx"
            ),
            models.Index(
                fields=["is_published", "show_on_home", "-created_at"],
                name="catalog_veh_pub_home_idx",
            ),
            models.Index(
                fields=["is_published", "body_type"],
                name="catalog_veh_pub_body_idx",
            ),
        ]

    def __str__(self):
        return f"{self.brand.name} {self.title}"

    def get_absolute_url(self):
        return reverse("catalog:vehicle_detail", kwargs={"slug": self.slug})

    @property
    def cny_rate_display(self) -> str:
        try:
            quantized = Decimal(self.cny_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, TypeError):
            quantized = Decimal("12.48")
        return f"{quantized:.2f}"

    @property
    def turnkey_price_note(self) -> str:
        return (
            f"Цена под ключ до Благовещенска по курсу {self.cny_rate_display}. "
            "Актуальную цену на день заявки уточняйте у менеджера."
        )

    @property
    def spec_sheet(self):
        from .spec_sheet import parse_spec_sheet

        return parse_spec_sheet(self.description or "")

    EXTRA_SPEC_SKIP = frozenset(
        {
            "color",
            "colour",
            "transmission",
            "gearbox",
            "vehicletransmission",
            "bodytype",
            "body",
            "horsepower",
            "power",
            "mileage",
            "year",
            "brand",
            "model",
            "title",
            "fueltype",
            "fuel",
            "enginetype",
            "vehicleengine",
            # Internal / Avito import plumbing — never show on the public card.
            "avitoimageurls",
        }
    )
    EXTRA_SPEC_LABELS = {
        "enginevol": "Объём двигателя",
        "enginesize": "Объём двигателя",
        "range": "Запас хода",
        "generation": "Поколение",
        "modification": "Модификация",
        "complectation": "Комплектация",
        "vin": "VIN",
        "owners": "Владельцев по ПТС",
        "pts": "ПТС",
        "drive": "Привод",
        "doors": "Дверей",
        "wheel": "Руль",
        "accident": "Состояние",
    }

    @property
    def extra_spec_cards(self) -> list[tuple[str, str]]:
        """Spec cards that are not already shown as dedicated Russian fields."""
        specs = self.specs if isinstance(self.specs, dict) else {}
        cards: list[tuple[str, str]] = []
        for key, value in specs.items():
            key_str = str(key or "").strip()
            # Hidden/internal keys (e.g. _avito_image_urls).
            if key_str.startswith("_"):
                continue
            if isinstance(value, (list, dict, tuple)):
                continue
            text = str(value or "").strip()
            if not text:
                continue
            # Guard: raw URL dumps accidentally stored as a string.
            if text.startswith("[") and "http" in text.lower():
                continue
            norm = "".join(ch for ch in key_str.lower() if ch.isalnum())
            if norm in self.EXTRA_SPEC_SKIP:
                continue
            label = self.EXTRA_SPEC_LABELS.get(norm) or key_str
            cards.append((label, text))
        return cards

    def _sync_color_from_specs(self) -> None:
        """Fill empty color from specs JSON so filters/facets stay index-friendly."""
        if (self.color or "").strip():
            return
        if not isinstance(self.specs, dict):
            return
        specs_color = str(self.specs.get("color") or "").strip()
        if specs_color:
            self.color = specs_color[:60]

    def _sync_engine_type_from_specs(self) -> None:
        """Fill empty engine_type from common fuel/engine keys in specs."""
        if (self.engine_type or "").strip():
            return
        if not isinstance(self.specs, dict):
            return
        from .engine_type import detect_engine_type

        for key in ("fuelType", "fuel_type", "fuel", "engine_type", "engineType"):
            raw = str(self.specs.get(key) or "").strip()
            if not raw:
                continue
            detected = detect_engine_type(raw)
            if detected:
                self.engine_type = detected
                return

    def save(self, *args, skip_image_queue=False, **kwargs):
        if self.description:
            self.description = sanitize_html(self.description)

        self._sync_color_from_specs()
        self._sync_engine_type_from_specs()

        # Auto-slug with collision prevention and IntegrityError retry
        if not self.slug:
            self.slug = build_unique_vehicle_slug(self.title, pk=self.pk)
        elif len(self.slug) > VEHICLE_SLUG_MAX_LENGTH:
            self.slug = build_unique_vehicle_slug(self.slug, pk=self.pk)

        update_fields = kwargs.get("update_fields")
        price_touch_fields = {
            "price_cny",
            "price_rub",
            "cny_rate",
            "is_currency_fixed",
        }
        should_price = update_fields is None or bool(
            price_touch_fields.intersection(update_fields)
        )
        if should_price:
            from .currency import apply_currency_pricing

            pricing_changed = apply_currency_pricing(self)
            if update_fields is not None and pricing_changed:
                kwargs["update_fields"] = list(
                    set(update_fields) | set(pricing_changed)
                )

        touch_image = update_fields is None or "main_image" in (
            kwargs.get("update_fields") or update_fields or []
        )
        old_image_name = ""
        if touch_image and self.pk:
            old_image_name = (
                Vehicle.objects.filter(pk=self.pk)
                .values_list("main_image", flat=True)
                .first()
                or ""
            )

        async_on = (
            getattr(settings, "IMAGE_PROCESSING_ASYNC", False)
            and not skip_image_queue
        )
        process_now = touch_image and self.main_image and should_process_image(
            self.main_image
        )
        # Sync path (tests / IMAGE_PROCESSING_ASYNC=False): convert before first write.
        if process_now and not async_on:
            processed_image = process_image_to_webp(self.main_image)
            if processed_image:
                self.main_image = processed_image

        try:
            super().save(*args, **kwargs)
        except IntegrityError:
            # Slug race condition: another request saved the same slug between check and save
            suffix = f"-{uuid.uuid4().hex[:6]}"
            base = (self.slug or "vehicle")[
                : VEHICLE_SLUG_MAX_LENGTH - len(suffix)
            ].rstrip("-")
            self.slug = f"{base}{suffix}"
            super().save(*args, **kwargs)

        new_name = getattr(self.main_image, "name", "") or ""
        if old_image_name and old_image_name != new_name:
            delete_responsive_variants(old_image_name)

        if not (touch_image and self.main_image and (process_now or old_image_name != new_name)):
            return

        if async_on:
            from .tasks import enqueue_process_vehicle_main_image

            enqueue_process_vehicle_main_image(self.pk)
            return

        write_responsive_variants(self.main_image)


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="gallery",
        verbose_name="Автомобиль",
    )
    image = models.ImageField(
        "Изображение", upload_to=vehicle_photo_path, max_length=255
    )
    order = models.PositiveIntegerField("Порядок вывода", default=0)

    class Meta:
        verbose_name = "Фото галереи"
        verbose_name_plural = "Фото галереи"
        ordering = ["order"]

    def __str__(self):
        return f"Фото для {self.vehicle.title}"

    def save(self, *args, skip_image_queue=False, **kwargs):
        update_fields = kwargs.get("update_fields")
        touch_image = update_fields is None or "image" in update_fields
        old_image_name = ""
        if touch_image and self.pk:
            old_image_name = (
                VehicleImage.objects.filter(pk=self.pk)
                .values_list("image", flat=True)
                .first()
                or ""
            )

        async_on = (
            getattr(settings, "IMAGE_PROCESSING_ASYNC", False)
            and not skip_image_queue
        )
        process_now = touch_image and self.image and should_process_image(self.image)
        if process_now and not async_on:
            processed_image = process_image_to_webp(self.image)
            if processed_image:
                self.image = processed_image

        super().save(*args, **kwargs)

        new_name = getattr(self.image, "name", "") or ""
        if old_image_name and old_image_name != new_name:
            delete_responsive_variants(old_image_name)

        if not (touch_image and self.image and (process_now or old_image_name != new_name)):
            return

        if async_on:
            from .tasks import enqueue_process_gallery_image

            enqueue_process_gallery_image(self.pk)
            return

        write_responsive_variants(self.image)
