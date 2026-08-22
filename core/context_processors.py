from django.conf import settings
from django.templatetags.static import static

from catalog.cache_helpers import review_aggregate
from utils.seo import absolute_url, canonical_url_for_request, site_base_url


def seo(request):
    """Default canonical / Open Graph values for templates."""
    path = (getattr(request, "path", "") or "").lower()
    skip_heavy_seo = (
        path == "/robots.txt"
        or path == "/sitemap.xml"
        or path.startswith("/sitemap-")
    )
    return {
        "SITE_URL": site_base_url(),
        "canonical_url": canonical_url_for_request(request),
        "sitemap_url": absolute_url("/sitemap.xml"),
        "default_og_image_url": absolute_url(static("images/pwa/icon-512.png")),
        "og_image_width": "512",
        "og_image_height": "512",
        "review_aggregate": None if skip_heavy_seo else review_aggregate(),
        "GOOGLE_SITE_VERIFICATION": getattr(
            settings, "GOOGLE_SITE_VERIFICATION", ""
        ),
        "YANDEX_VERIFICATION": getattr(settings, "YANDEX_VERIFICATION", ""),
        "YANDEX_METRIKA_ID": getattr(settings, "YANDEX_METRIKA_ID", ""),
        "SEO_MODEL_PAGES_ENABLED": getattr(settings, "SEO_MODEL_PAGES_ENABLED", False),
    }
