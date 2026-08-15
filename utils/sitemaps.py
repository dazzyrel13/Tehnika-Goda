"""Sitemap base that uses SITE_URL instead of django.contrib.sites defaults."""

from django.contrib.sitemaps import Sitemap

from utils.seo import site_domain, site_protocol


class SiteUrlSitemap(Sitemap):
    def get_protocol(self, protocol=None):
        return site_protocol()

    def get_domain(self, site=None):
        return site_domain()
