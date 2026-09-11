from django.contrib import admin
from django.utils.html import format_html

from .models import PromoBanner, Review, ReviewPlatformSettings


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = (
        "preview",
        "title",
        "teaser",
        "is_published",
        "sort_order",
        "updated_at",
    )
    list_display_links = ("preview", "title")
    list_editable = ("is_published", "sort_order")
    list_filter = ("is_published",)
    search_fields = ("title", "teaser", "link_url")
    ordering = ("sort_order", "-updated_at")
    readonly_fields = ("preview_large", "updated_at")
    fieldsets = (
        (
            "Акция",
            {
                "fields": (
                    "title",
                    "teaser",
                    "image",
                    "preview_large",
                    "link_url",
                ),
                "description": (
                    "Баннер автоматически сжимается в WebP. "
                    "На главной показываются опубликованные акции (порядок — поле ниже)."
                ),
            },
        ),
        (
            "Публикация",
            {"fields": ("is_published", "sort_order", "updated_at")},
        ),
    )

    @admin.display(description="Превью")
    def preview(self, obj: PromoBanner):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="height:48px;width:auto;border-radius:4px;" />',
            obj.image.url,
        )

    @admin.display(description="Баннер")
    def preview_large(self, obj: PromoBanner):
        if not obj.pk or not obj.image:
            return "Сохраните, чтобы увидеть превью"
        return format_html(
            '<img src="{}" alt="" style="max-width:360px;height:auto;border-radius:8px;" />',
            obj.image.url,
        )


@admin.register(ReviewPlatformSettings)
class ReviewPlatformSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Ссылки на профили компании",
            {
                "fields": ("yandex_url", "twogis_url", "avito_url"),
                "description": (
                    "Эти ссылки делают кликабельными виджеты Яндекс / 2ГИС / Авито "
                    "внизу блока отзывов на главной. "
                    "Тексты отзывов сами по себе не появляются — их нужно добавить "
                    "отдельно в разделе «Отзывы клиентов» (имя, текст, оценка, площадка). "
                    "Вставьте полные URL (https://…)."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not ReviewPlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        from django.urls import reverse

        obj = ReviewPlatformSettings.load()
        return redirect(
            reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                args=[obj.pk],
            )
        )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "client_name",
        "city",
        "source",
        "rating",
        "date",
        "is_published",
        "order",
    )
    list_display_links = ("client_name",)
    list_filter = ("source", "is_published", "rating", "date")
    search_fields = ("client_name", "city", "comment", "vehicle_purchased", "source_url")
    list_editable = ("is_published", "order", "rating")
    ordering = ("order", "-date")
    date_hierarchy = "date"
    list_per_page = 25
    actions = ("publish_reviews", "unpublish_reviews")
    fieldsets = (
        (
            "Отзыв",
            {
                "fields": (
                    "client_name",
                    "city",
                    "vehicle_purchased",
                    "avatar",
                    "comment",
                    "rating",
                    "date",
                ),
                "description": (
                    "На главной показываются до 6 опубликованных отзывов "
                    "(сортировка: порядок, затем дата). "
                    "Сюда нужно вручную добавить текст отзыва — "
                    "сайт не подтягивает его автоматически по ссылке."
                ),
            },
        ),
        (
            "Публикация",
            {
                "fields": ("is_published", "order"),
            },
        ),
        (
            "Источник",
            {
                "fields": ("source", "source_url"),
                "description": (
                    "Выберите площадку: 2ГИС, Авито или Яндекс Карты. "
                    "Если ссылка на отзыв пустая — используется общая ссылка "
                    "из раздела «Ссылки на отзывы»."
                ),
            },
        ),
    )

    @admin.action(description="Опубликовать выбранные отзывы")
    def publish_reviews(self, request, queryset):
        updated = queryset.update(is_published=True)
        from catalog.cache_helpers import invalidate_home_reviews_cache

        invalidate_home_reviews_cache()
        self.message_user(request, f"Опубликовано отзывов: {updated}")

    @admin.action(description="Снять с публикации")
    def unpublish_reviews(self, request, queryset):
        updated = queryset.update(is_published=False)
        from catalog.cache_helpers import invalidate_home_reviews_cache

        invalidate_home_reviews_cache()
        self.message_user(request, f"Снято с публикации: {updated}")
