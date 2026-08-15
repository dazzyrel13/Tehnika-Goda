from django.contrib import admin

from .models import Review, ReviewPlatformSettings


@admin.register(ReviewPlatformSettings)
class ReviewPlatformSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Ссылки на профили компании",
            {
                "fields": ("yandex_url", "twogis_url", "avito_url"),
                "description": (
                    "Эти ссылки открываются из виджетов рейтингов на главной "
                    "и используются как запасной вариант, если у конкретного "
                    "отзыва не указана своя ссылка. "
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
                    "comment",
                    "rating",
                    "date",
                ),
                "description": (
                    "На главной показываются до 6 опубликованных отзывов "
                    "(сортировка: порядок, затем дата)."
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
        self.message_user(request, f"Опубликовано отзывов: {updated}")

    @admin.action(description="Снять с публикации")
    def unpublish_reviews(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"Снято с публикации: {updated}")
