from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"

    def ready(self):
        from core.admin_cleanup import configure_admin_branding, simplify_admin_registry

        from . import signals  # noqa: F401

        simplify_admin_registry()
        configure_admin_branding()
