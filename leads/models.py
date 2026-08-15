from django.db import models

from catalog.models import Vehicle


class Inquiry(models.Model):
    STATUS_CHOICES = [
        ("new", "Новая"),
        ("process", "В работе"),
        ("completed", "Завершена"),
        ("canceled", "Отмена"),
    ]

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Интересующий автомобиль",
        related_name="inquiries",
    )
    name = models.CharField("Имя клиента", max_length=100)
    phone = models.CharField("Телефон/Telegram", max_length=20)
    city = models.CharField("Город", max_length=120, default="Не указан")
    message = models.TextField("Сообщение", blank=True)

    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="new"
    )
    source = models.CharField("Источник (URL/Кампания)", max_length=255, blank=True)
    referer = models.CharField("Referer", max_length=500, blank=True)
    utm_source = models.CharField("UTM Source", max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField("UTM Medium", max_length=100, blank=True, db_index=True)
    utm_campaign = models.CharField(
        "UTM Campaign", max_length=120, blank=True, db_index=True
    )
    visitor_id = models.CharField("ID посетителя", max_length=64, blank=True, db_index=True)
    session_key = models.CharField("Сессия", max_length=64, blank=True, db_index=True)

    created_at = models.DateTimeField("Дата заявки", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Заявка (Лид)"
        verbose_name_plural = "Заявки (Лиды)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заявка от {self.name} ({self.created_at.strftime('%d.%m %H:%M')})"
