"""Project-level Django app config (signals, startup hooks)."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    label = "core_config"

    def ready(self):
        import core.admin_login_approval  # noqa: F401 — register auth signals
