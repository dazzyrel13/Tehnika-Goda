import os
from io import BytesIO

from django import forms
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.db.models import Max
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import slugify
from PIL import Image
from unidecode import unidecode

from utils.safe_http import fetch_url_bytes, is_safe_request_url

from .cache_helpers import invalidate_vehicle_public_caches
from .models import (
    Brand,
    Category,
    InspectionReport,
    Vehicle,
    VehicleImage,
)
from .parser_service import EliteVehicleParser


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Поле для выбора сразу нескольких файлов (Django docs)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(
                attrs={
                    "multiple": True,
                    "accept": "image/*",
                    "class": "tg-gallery-multi-input",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = []
            for item in data:
                cleaned = single_clean(item, initial)
                if cleaned:
                    result.append(cleaned)
            return result
        cleaned = single_clean(data, initial)
        return [cleaned] if cleaned else []


class VehicleAdminForm(forms.ModelForm):
    gallery_images = MultipleFileField(
        required=False,
        label="Галерея — загрузить пачкой",
        help_text=(
                    "Зажмите Ctrl (⌘ на Mac) или Shift и выберите сразу много фото. "
                    "Либо выделите пачку в проводнике мышкой. "
                    "Не больше ~30 снимков за раз (тяжёлые JPEG лучше пачками). "
                    "После сохранения порядок меняется перетаскиванием фото ниже."
        ),
    )

    class Meta:
        model = Vehicle
        exclude = (
            "slug",
            "model",
            "specs",
            "price_cny",
            "is_currency_fixed",
            "badge_text",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].help_text = "Например: Zeekr 001 2024 FR"
        self.fields["price_rub"].label = "Цена, ₽"
        self.fields["price_rub"].help_text = (
            "Цена для сайта в рублях. Рядом укажите курс юаня — он выводится под ценой."
        )
        self.fields["cny_rate"].label = "Курс юаня"
        self.fields["cny_rate"].help_text = (
            "Сколько рублей за 1 юань. На сайте: «по курсу 12.48»."
        )
        self.fields["main_image"].label = "Основное фото (обложка)"
        self.fields["main_image"].help_text = (
            "Крупное фото на карточке и первое в галерее внутри объявления. "
            "Если пусто — возьмём первое фото из пачки ниже."
        )
        self.fields["mileage"].help_text = "0 — для новых авто"
        self.fields["description"].label = "Описание комплектации"
        self.fields["description"].help_text = (
            "Вставьте текст строками, как в коммерческом предложении. "
            "Слева поле в скобках, справа значение — на сайте станет таблица. "
            "Пример:\n"
            "[Название автомобиля] Volkswagen Bora\n"
            "【Цвет】 серый\n"
            "[Пробег] 30 000 километров"
        )


@admin.register(InspectionReport)
class InspectionReportAdmin(admin.ModelAdmin):
    list_display = ("report_uid", "title", "is_verified", "created_at")
    search_fields = ("report_uid", "title")
    list_filter = ("is_verified", "created_at")
    readonly_fields = ("report_uid", "created_at")
    fields = (
        "report_uid",
        "title",
        "pdf_file",
        "dealer_verdict",
        "is_verified",
        "created_at",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    fields = ("name", "parent")
    ordering = ("name",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "parent" in form.base_fields:
            form.base_fields["parent"].required = False
            form.base_fields["parent"].help_text = (
                "Необязательно. Например: «Седаны» → родитель «Легковые»."
            )
        return form


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("display_logo", "name")
    search_fields = ("name",)
    fields = ("name", "logo")
    ordering = ("name",)

    def display_logo(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit: contain;" />',
                obj.logo.url,
            )
        return "—"

    display_logo.short_description = "Лого"


class VehicleImageInline(admin.StackedInline):
    model = VehicleImage
    extra = 0
    template = "admin/edit_inline/vehicleimage_grid.html"
    fields = ("image", "order")
    ordering = ("order", "id")
    verbose_name = "Фото"
    verbose_name_plural = "Галерея"

    class Media:
        js = ("admin/js/vehicleimage_inline_sort.js",)
        css = {"all": ("admin/css/vehicleimage_inline.css",)}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "order":
            kwargs["widget"] = forms.HiddenInput()
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    form = VehicleAdminForm
    list_display = (
        "display_image",
        "title",
        "brand",
        "year",
        "price_rub",
        "is_published",
        "is_featured",
    )
    list_filter = (
        "brand",
        "category",
        "is_published",
        "is_featured",
        "year",
    )
    search_fields = ("title", "brand__name", "model", "description", "color")
    autocomplete_fields = ("brand", "category", "report")
    inlines = [VehicleImageInline]
    list_editable = ("is_published", "is_featured", "price_rub")
    list_per_page = 25
    save_on_top = False
    actions = [
        "mark_featured",
        "unmark_featured",
        "publish_selected",
        "unpublish_selected",
    ]

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    ("brand", "category"),
                    "title",
                    ("year", "mileage", "horsepower"),
                    ("transmission", "body_type", "color"),
                ),
                "description": (
                    "Нужной марки нет в списке? Нажмите «+» рядом с полем «Марка» "
                    "и добавьте её в окне — без ухода со страницы."
                ),
            },
        ),
        (
            "Цена и статус",
            {
                "fields": (
                    ("price_rub", "cny_rate"),
                    ("is_published", "is_featured"),
                ),
                "description": (
                    "Новые карточки и импорт по URL по умолчанию скрыты. "
                    "Курс юаня меняйте, когда цена в рублях уже не совпадает с расчётом. "
                    "«Выкупленный» — тёмная плашка на сайте и попадание в фильтр "
                    "«Выкупленные». При пробеге 0 км автоматически показывается "
                    "плашка «Новый»."
                ),
            },
        ),
        (
            "Фото и описание",
            {
                "fields": (
                    "gallery_images",
                    "main_image",
                    "description",
                ),
                "description": (
                    "Сначала загрузите пачку фото в «Галерея». "
                    "Обложку можно не указывать — подставится первое фото. "
                    "Порядок на сайте: после сохранения схватите фото в сетке и перетащите. "
                    "Описание — вставьте строки «[Поле] значение», сайт сам сделает два столбца."
                ),
            },
        ),
        (
            "Цифровой отчёт",
            {
                "fields": ("report",),
                "description": (
                    "Создайте отчёт в разделе «Цифровые отчеты», затем привяжите сюда. "
                    "На сайте появится досье и PDF."
                ),
            },
        ),
    )

    class Media:
        css = {"all": ("admin/css/vehicleimage_inline.css",)}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "description":
            kwargs["widget"] = forms.Textarea(
                attrs={
                    "rows": 20,
                    "cols": 80,
                    "class": "vLargeTextField tg-spec-paste",
                    "placeholder": (
                        "[Название автомобиля] Volkswagen Bora (099526)\n"
                        "[Модель] Версия 2023 200TSI DSG Smart Travel PRO\n"
                        "【Режим привода】 2WD\n"
                        "【Цвет】 серый"
                    ),
                }
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        vehicle = form.instance

        # Сначала cleaned_data (MultipleFileField), иначе сырой getlist
        uploaded = form.cleaned_data.get("gallery_images") or []
        if not isinstance(uploaded, (list, tuple)):
            uploaded = [uploaded] if uploaded else []
        if not uploaded:
            uploaded = request.FILES.getlist("gallery_images")

        if uploaded:
            max_order = (
                vehicle.gallery.aggregate(max_order=Max("order")).get("max_order") or 0
            )
            added = 0
            for index, image in enumerate(uploaded, start=1):
                try:
                    probe = Image.open(image)
                    probe.verify()
                    image.seek(0)
                except Exception:
                    continue
                VehicleImage.objects.create(
                    vehicle=vehicle,
                    image=image,
                    order=max_order + index,
                )
                added += 1
            if added:
                self.message_user(
                    request,
                    f"В галерею добавлено фото: {added}. "
                    "Перетащите строки, если нужно изменить порядок, и сохраните ещё раз.",
                )
            skipped = len(uploaded) - added
            if skipped:
                self.message_user(
                    request,
                    f"Пропущено файлов (не изображение): {skipped}.",
                    level=messages.WARNING,
                )

        # Обложка из первого фото галереи, если не задана вручную
        vehicle.refresh_from_db()
        if not vehicle.main_image:
            first = vehicle.gallery.order_by("order", "id").first()
            if first and first.image:
                vehicle.main_image = first.image
                vehicle.save(update_fields=["main_image"])

    def display_image(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" width="80" style="border-radius: 5px;" />',
                obj.main_image.url,
            )
        return "Нет фото"

    display_image.short_description = "Фото"

    @admin.action(description="Отметить как выкупленные")
    def mark_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        invalidate_vehicle_public_caches()
        self.message_user(request, f"Выкупленные: {updated}")

    @admin.action(description="Снять метку «Выкупленный»")
    def unmark_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        invalidate_vehicle_public_caches()
        self.message_user(request, f"Снято с выкупленных: {updated}")

    @admin.action(description="Опубликовать выбранные")
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True)
        invalidate_vehicle_public_caches()
        self.message_user(request, f"Опубликовано: {updated}")

    @admin.action(description="Снять выбранные с публикации")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False)
        invalidate_vehicle_public_caches()
        self.message_user(request, f"Снято с публикации: {updated}")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "parse-url/",
                self.admin_site.admin_view(self.parse_url_view),
                name="catalog_vehicle_parse_url",
            ),
        ]
        return custom_urls + urls

    def parse_url_view(self, request):
        if request.method == "POST":
            url = request.POST.get("url")
            if url:
                data = EliteVehicleParser.parse_from_url(url)
                if data:
                    brand_name = data.get("brand_name") or "Unknown"
                    brand, _ = Brand.objects.get_or_create(
                        name=brand_name,
                        defaults={"slug": slugify(unidecode(brand_name))},
                    )

                    category = (
                        Category.objects.filter(slug="cars_new").first()
                        or Category.objects.all().first()
                    )

                    title = f"{brand.name} {data['model_name']} {data['year'] or ''}".strip()
                    base_slug = slugify(unidecode(title))
                    unique_slug = base_slug

                    num = 1
                    while Vehicle.objects.filter(slug=unique_slug).exists():
                        unique_slug = f"{base_slug}-{num}"
                        num += 1

                    vehicle = Vehicle.objects.create(
                        title=title,
                        brand=brand,
                        category=category,
                        model=data["model_name"],
                        year=data["year"] or 0,
                        mileage=data.get("mileage", 0),
                        horsepower=data.get("horsepower"),
                        transmission=(
                            data.get("specs", {}).get("transmission")
                            or data.get("specs", {}).get("gearbox")
                            or ""
                        ),
                        body_type=data.get("body_type", ""),
                        color=data.get("specs", {}).get("color", ""),
                        price_rub=data["price_rub"],
                        description=data["description"],
                        specs=data.get("specs", {}),
                        slug=unique_slug,
                        is_published=False,
                    )

                    image_url = data.get("main_image_url")
                    if image_url and is_safe_request_url(image_url):
                        try:
                            raw, _final_url = fetch_url_bytes(
                                image_url,
                                max_bytes=15 * 1024 * 1024,
                                timeout=10,
                            )
                            img = Image.open(BytesIO(raw))
                            img.verify()
                            img = Image.open(BytesIO(raw))
                            fmt = (img.format or "JPEG").upper()
                            ext_map = {
                                "JPEG": ".jpg",
                                "JPG": ".jpg",
                                "PNG": ".png",
                                "WEBP": ".webp",
                            }
                            ext = ext_map.get(fmt, ".jpg")
                            path_ext = (
                                os.path.splitext(image_url.split("?")[0])[1].lower()
                            )
                            if path_ext in (".jpg", ".jpeg", ".png", ".webp"):
                                ext = ".jpg" if path_ext == ".jpeg" else path_ext

                            vehicle.main_image.save(
                                f"imported_{vehicle.id}{ext}",
                                ContentFile(raw),
                                save=True,
                            )
                        except Exception as e:
                            self.message_user(
                                request,
                                f"Не удалось скачать фото для {vehicle.title}: {e}",
                                level=messages.WARNING,
                            )

                    messages.success(
                        request,
                        f"Авто «{vehicle.title}» импортировано как черновик. "
                        "Проверьте цену и категорию, затем опубликуйте.",
                    )
                    return redirect(
                        reverse("admin:catalog_vehicle_change", args=[vehicle.id])
                    )
                else:
                    messages.error(
                        request,
                        "Не удалось разобрать объявление по этой ссылке. Проверьте адрес.",
                    )
            return redirect(reverse("admin:catalog_vehicle_changelist"))

        return render(request, "admin/catalog/parse_form.html")
