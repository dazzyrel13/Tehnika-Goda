"""Упрощение админки: только каталог авто и связанное."""

from django.contrib import admin


# Что оставляем в меню админки
KEEP_LABELS = {
    "auth.user",
    "catalog.brand",
    "catalog.category",
    "catalog.vehicle",
    "catalog.inspectionreport",
    "content.review",
    "content.reviewplatformsettings",
    "leads.inquiry",
}


def simplify_admin_registry():
    """Снимает с регистрации всё, кроме моделей каталога/заявок/пользователей."""
    for model in list(admin.site._registry.keys()):
        label = model._meta.label_lower
        if label not in KEEP_LABELS:
            try:
                admin.site.unregister(model)
            except admin.sites.NotRegistered:
                pass


def configure_admin_branding():
    admin.site.site_header = "Техника Года — Каталог"
    admin.site.site_title = "Техника Года"
    admin.site.index_title = "Автомобили и заявки"

    if getattr(admin.site, "_tg_index_patched", False):
        return

    _original_index = admin.site.index

    def index_with_stats(request, extra_context=None):
        from catalog.models import Vehicle
        from leads.models import Inquiry

        extra_context = extra_context or {}
        extra_context.update(
            {
                "tg_vehicles_count": Vehicle.objects.count(),
                "tg_published_count": Vehicle.objects.filter(is_published=True).count(),
                "tg_new_leads_count": Inquiry.objects.filter(status="new").count(),
            }
        )
        return _original_index(request, extra_context)

    admin.site.index = index_with_stats
    admin.site._tg_index_patched = True


def configure_admin():
    simplify_admin_registry()
    configure_admin_branding()
