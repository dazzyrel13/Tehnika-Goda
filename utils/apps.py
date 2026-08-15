from django.apps import AppConfig


class UtilsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utils"

    def ready(self):
        # Global Pillow guard (admin uploads, parser, image_processing).
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 40_000_000

        from core.compat import patch_django_template_context_copy

        patch_django_template_context_copy()

        from django.db.models.signals import post_migrate

        from utils.seo import sync_site_from_settings

        def _sync_site(**kwargs):
            sync_site_from_settings()

        post_migrate.connect(
            _sync_site, dispatch_uid="utils.sync_site_from_settings"
        )
