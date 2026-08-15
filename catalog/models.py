import os
import uuid

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


def vehicle_photo_path(instance, filename):
    return f"catalog/vehicles/{instance.vehicle.slug}/{filename}"


# Custom save path for main image


def vehicle_main_photo_path(instance, filename):
    return f"catalog/vehicles/{instance.slug}/main_{filename}"


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

    # Pricing
    price_cny = models.DecimalField(
        "Цена в CNY",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        db_index=True,
    )
    price_rub = models.DecimalField(
        "Цена, ₽",
        max_digits=15,
        decimal_places=0,
        blank=True,
        null=True,
        help_text="Цена для сайта в рублях",
        db_index=True,
    )
    is_currency_fixed = models.BooleanField("Зафиксировать цену", default=False)

    # Specs & Description
    description = models.TextField("Описание", blank=True)
    specs = models.JSONField(
        "Технические характеристики (ТТХ)",
        default=dict,
        help_text="Например: {'power': '422 л.с.', 'range': '600 км'}",
    )

    # Media
    main_image = models.ImageField(
        "Основное фото", upload_to=vehicle_main_photo_path, blank=True, null=True
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
    badge_text = models.CharField(
        "Текст на бэйдже",
        max_length=20,
        blank=True,
        help_text="Свой текст плашки (если не «Новый» / «Выкупленные»). Например: В ПУТИ",
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
                fields=["is_published", "is_featured", "-created_at"],
                name="catalog_veh_pub_feat_idx",
            ),
            models.Index(
                fields=["is_published", "mileage"], name="catalog_veh_pub_mile_idx"
            ),
        ]

    def __str__(self):
        return f"{self.brand.name} {self.title}"

    def get_absolute_url(self):
        return reverse("catalog:vehicle_detail", kwargs={"slug": self.slug})

    def _sync_color_from_specs(self) -> None:
        """Fill empty color from specs JSON so filters/facets stay index-friendly."""
        if (self.color or "").strip():
            return
        if not isinstance(self.specs, dict):
            return
        specs_color = str(self.specs.get("color") or "").strip()
        if specs_color:
            self.color = specs_color[:60]

    def save(self, *args, **kwargs):
        if self.description:
            self.description = sanitize_html(self.description)

        self._sync_color_from_specs()

        # Auto-slug with collision prevention and IntegrityError retry
        if not self.slug:
            base_slug = slugify(unidecode(self.title))
            slug = base_slug
            num = 1
            while Vehicle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug

        update_fields = kwargs.get("update_fields")
        touch_image = update_fields is None or "main_image" in update_fields
        old_image_name = ""
        if touch_image and self.pk:
            old_image_name = (
                Vehicle.objects.filter(pk=self.pk)
                .values_list("main_image", flat=True)
                .first()
                or ""
            )
        process_now = touch_image and self.main_image and should_process_image(
            self.main_image
        )
        if process_now:
            processed_image = process_image_to_webp(self.main_image)
            if processed_image:
                self.main_image = processed_image
        try:
            super().save(*args, **kwargs)
        except IntegrityError:
            # Slug race condition: another request saved the same slug between check and save
            self.slug = f"{self.slug}-{uuid.uuid4().hex[:6]}"
            super().save(*args, **kwargs)
        new_name = getattr(self.main_image, "name", "") or ""
        if old_image_name and old_image_name != new_name:
            delete_responsive_variants(old_image_name)
        if touch_image and self.main_image and (process_now or old_image_name != new_name):
            write_responsive_variants(self.main_image)


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="gallery",
        verbose_name="Автомобиль",
    )
    image = models.ImageField("Изображение", upload_to=vehicle_photo_path)
    order = models.PositiveIntegerField("Порядок вывода", default=0)

    class Meta:
        verbose_name = "Фото галереи"
        verbose_name_plural = "Фото галереи"
        ordering = ["order"]

    def __str__(self):
        return f"Фото для {self.vehicle.title}"

    def save(self, *args, **kwargs):
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
        process_now = touch_image and self.image and should_process_image(self.image)
        if process_now:
            processed_image = process_image_to_webp(self.image)
            if processed_image:
                self.image = processed_image
        super().save(*args, **kwargs)
        new_name = getattr(self.image, "name", "") or ""
        if old_image_name and old_image_name != new_name:
            delete_responsive_variants(old_image_name)
        if touch_image and self.image and (process_now or old_image_name != new_name):
            write_responsive_variants(self.image)
