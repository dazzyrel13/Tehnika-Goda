from django.contrib import admin

from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "name",
        "phone",
        "status",
        "vehicle",
        "city",
    )
    list_filter = ("status", "created_at")
    search_fields = ("name", "phone", "message", "city", "vehicle__title")
    list_editable = ("status",)
    list_display_links = ("name",)
    date_hierarchy = "created_at"
    autocomplete_fields = ("vehicle",)
    list_select_related = ("vehicle", "vehicle__brand")
    list_per_page = 30
    ordering = ("-created_at",)
    actions = [
        "mark_process",
        "mark_completed",
        "mark_canceled",
    ]

    readonly_fields = (
        "created_at",
        "updated_at",
        "source",
        "referer",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "visitor_id",
        "session_key",
    )

    fieldsets = (
        (
            "Заявка",
            {
                "fields": (
                    "status",
                    ("name", "phone"),
                    "city",
                    "vehicle",
                    "message",
                    "created_at",
                )
            },
        ),
        (
            "Служебное",
            {
                "classes": ("collapse",),
                "fields": (
                    "source",
                    "referer",
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                    "visitor_id",
                    "session_key",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.action(description="Статус: В работе")
    def mark_process(self, request, queryset):
        updated = queryset.update(status="process")
        self.message_user(request, f"В работе: {updated}")

    @admin.action(description="Статус: Завершена")
    def mark_completed(self, request, queryset):
        updated = queryset.update(status="completed")
        self.message_user(request, f"Завершено: {updated}")

    @admin.action(description="Статус: Отмена")
    def mark_canceled(self, request, queryset):
        updated = queryset.update(status="canceled")
        self.message_user(request, f"Отменено: {updated}")
