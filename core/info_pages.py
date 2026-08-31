"""SEO and JSON-LD context for static info pages."""

from __future__ import annotations

from django.templatetags.static import static as static_url
from django.views.generic import TemplateView

from utils.seo import absolute_url, build_article_json_ld, serialize_json_ld

_INFO_PAGES = {
    "leasing": {
        "seo_title": "Лизинг коммерческого транспорта и спецтехники | Техника Года",
        "seo_description": (
            "Лизинг коммерческого транспорта и спецтехники из Китая: "
            "ориентировочный расчёт платежа и подбор программы у лизинговых компаний."
        ),
        "article_headline": "Лизинг коммерческого транспорта и спецтехники",
        "date_published": "2024-08-01",
        "date_modified": "2026-08-01",
    },
    "about": {
        "seo_title": "О компании Техника Года — площадка в Китае и выдача в Благовещенске",
        "seo_description": (
            "Техника Года: своя площадка в Китае, проверка до оплаты, "
            "цена под ключ до Благовещенска, гарантия 6 месяцев на ДВС и КПП."
        ),
        "article_headline": "О компании Техника Года",
        "article_image": "images/team/leadership.webp",
        "date_published": "2024-06-01",
        "date_modified": "2026-08-01",
    },
    "privacy": {
        "seo_title": "Политика конфиденциальности | Техника Года",
        "seo_description": (
            "Политика конфиденциальности Техника Года: правила обработки "
            "персональных данных, цели сбора информации и меры защиты данных пользователей."
        ),
        "article_headline": "Политика конфиденциальности",
        "date_published": "2024-06-01",
        "date_modified": "2026-08-01",
    },
    "services": {
        "seo_title": "Информация об услугах и прайс-лист | Техника Года",
        "seo_description": (
            "Услуга подбора и привоза автомобилей из Китая под ключ: порядок работы, "
            "этапы оплаты и пример прайс-листа. Выдача в Благовещенске."
        ),
        "article_headline": "Информация об услугах и прайс-лист",
        "date_published": "2025-03-01",
        "date_modified": "2026-08-01",
    },
}


class InfoPageView(TemplateView):
    page_key: str = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meta = _INFO_PAGES[self.page_key]
        page_url = absolute_url(self.request.path)
        image_path = meta.get("article_image")
        image_url = absolute_url(static_url(image_path)) if image_path else None
        article = build_article_json_ld(
            headline=meta["article_headline"],
            description=meta["seo_description"],
            url=page_url,
            date_published=meta["date_published"],
            date_modified=meta.get("date_modified"),
            image_url=image_url,
        )
        context.update(meta)
        context["article_json_ld"] = serialize_json_ld(article)
        return context
