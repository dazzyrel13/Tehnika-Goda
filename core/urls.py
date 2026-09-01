from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from two_factor.admin import AdminSiteOTPRequired
from two_factor.urls import urlpatterns as tf_urls

from catalog.sitemaps import (
    BrandSitemap,
    BrandsIndexSitemap,
    CarModelSitemap,
    CategorySitemap,
    VehicleSitemap,
)
from catalog.views import HomeView
from content.sitemaps import StaticViewSitemap
from core.health import healthz
from core.info_pages import InfoPageView
from core.media import serve_media

sitemaps = {
    "static": StaticViewSitemap,
    "vehicles": VehicleSitemap,
    "brands": BrandSitemap,
    "brands_index": BrandsIndexSitemap,
    "models": CarModelSitemap,
    "categories": CategorySitemap,
}

# Custom Admin branding is set in core.admin_cleanup (via CatalogConfig.ready)
# OTP is required for every staff session — do not use the stock admin login.
admin.site.__class__ = AdminSiteOTPRequired

from core.admin_url import DEFAULT_ADMIN_URL_PREFIX

def _admin_url_prefix() -> str:
    prefix = (settings.ADMIN_URL_PREFIX or DEFAULT_ADMIN_URL_PREFIX).lstrip("/")
    if not prefix.endswith("/"):
        prefix += "/"
    return prefix



urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # Old WordPress / WooCommerce URLs (Yandex still has them indexed).
    path("", include("core.legacy_redirects")),
    # 2FA login/setup lives under the hidden admin prefix (IP allowlist applies).
    path(_admin_url_prefix(), include(tf_urls)),
    path(_admin_url_prefix(), admin.site.urls),
    # Homepage at site root (legacy /catalog/ redirects inside catalog.urls)
    path("", HomeView.as_view(), name="home"),
    # Legacy blog URLs → home (feature removed)
    path("blog/", RedirectView.as_view(url="/", permanent=True)),
    path("content/blog/", RedirectView.as_view(url="/", permanent=True)),
    path(
        "content/blog/<slug:slug>/",
        RedirectView.as_view(url="/", permanent=True),
    ),
    # Legacy info pages → blocks on the home page
    path(
        "delivery/",
        RedirectView.as_view(url="/#delivery-estimate", permanent=True),
        name="delivery",
    ),
    path(
        "customs/",
        RedirectView.as_view(url="/#customs", permanent=True),
        name="customs",
    ),
    path(
        "how-to-buy/",
        RedirectView.as_view(url="/#how-we-work", permanent=True),
        name="how_to_buy",
    ),
    path(
        "leasing/",
        InfoPageView.as_view(
            template_name="info/leasing.html",
            page_key="leasing",
        ),
        name="leasing",
    ),
    path(
        "about/",
        InfoPageView.as_view(
            template_name="info/about.html",
            page_key="about",
        ),
        name="about",
    ),
    path(
        "privacy/",
        InfoPageView.as_view(
            template_name="info/privacy.html",
            page_key="privacy",
        ),
        name="privacy",
    ),
    path(
        "services/",
        InfoPageView.as_view(
            template_name="info/services.html",
            page_key="services",
        ),
        name="services",
    ),
    # Favicon at site root (browsers request /favicon.ico by default)
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=static_url("images/favicon.ico") + "?v=9",
            permanent=False,
        ),
        name="favicon",
    ),
    # PWA
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="sw.js", content_type="application/javascript"
        ),
        name="sw",
    ),
    path(
        "manifest.json",
        TemplateView.as_view(
            template_name="manifest.json", content_type="application/json"
        ),
        name="manifest",
    ),
    # SEO
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
            extra_context={
                "site_url": settings.SITE_URL.rstrip("/"),
            },
        ),
        name="robots",
    ),
    path(
        "google42cb08ac2dabb73c.html",
        TemplateView.as_view(
            template_name="google42cb08ac2dabb73c.html",
            content_type="text/html; charset=UTF-8",
        ),
        name="google_search_console",
    ),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    # Apps
    path("catalog/", include("catalog.urls", namespace="catalog")),
    path("leads/", include("leads.urls", namespace="leads")),
    path("content/", include("content.urls", namespace="content")),
    # CKEditor 5 image upload endpoint (required by admin widgets)
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    # Always serve uploads: production host nginx proxies /media/ to Gunicorn.
    path("media/<path:path>", serve_media, name="serve_media"),
]
