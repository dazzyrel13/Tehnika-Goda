from django.db import models


class VisitEvent(models.Model):
    visitor_id = models.CharField("ID посетителя", max_length=64, db_index=True)
    session_key = models.CharField("Сессия", max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField("IP", blank=True, null=True)
    user_agent = models.CharField("User-Agent", max_length=255, blank=True)
    path = models.CharField("Путь", max_length=255, db_index=True)
    referer = models.CharField("Источник", max_length=500, blank=True)
    utm_source = models.CharField("UTM Source", max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField("UTM Medium", max_length=100, blank=True, db_index=True)
    utm_campaign = models.CharField(
        "UTM Campaign", max_length=120, blank=True, db_index=True
    )
    vehicle = models.ForeignKey(
        "catalog.Vehicle",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="visit_events",
        verbose_name="Авто",
    )
    is_vehicle_page = models.BooleanField("Просмотр карточки авто", default=False, db_index=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Событие посещения"
        verbose_name_plural = "События посещений"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.path} @ {self.created_at:%d.%m.%Y %H:%M}"
