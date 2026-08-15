from django.urls import reverse

from utils.sitemaps import SiteUrlSitemap


class StaticViewSitemap(SiteUrlSitemap):
    """Ключевые страницы без записей в БД (лендинги, инфо, FAQ)."""

    _pages = (
        # (url_name, priority, changefreq)
        ("catalog:home", 1.0, "daily"),
        ("catalog:category", 0.9, "daily", {"category_slug": "cars"}),
        ("content:faq", 0.65, "weekly"),
        ("about", 0.6, "monthly"),
        ("leasing", 0.5, "monthly"),
        ("privacy", 0.4, "yearly"),
    )

    def items(self):
        return list(range(len(self._pages)))

    def location(self, item):
        entry = self._pages[item]
        name = entry[0]
        kwargs = entry[3] if len(entry) > 3 else {}
        return reverse(name, kwargs=kwargs)

    def priority(self, item):
        return self._pages[item][1]

    def changefreq(self, item):
        return self._pages[item][2]
