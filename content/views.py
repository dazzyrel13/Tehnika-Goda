from django.urls import reverse
from django.views.generic import TemplateView

from utils.seo import absolute_url, build_article_json_ld, serialize_json_ld

from .faq_defaults import DEFAULT_FAQS


class FAQListView(TemplateView):
    """Страница FAQ: текст из faq_defaults, без таблицы в БД."""

    template_name = "content/faq.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["faq_items"] = list(DEFAULT_FAQS)
        context["seo_title"] = "FAQ | Техника Года"
        context["seo_description"] = (
            "FAQ Техника Года: гарантия, цена под ключ, сроки ввоза, "
            "оплата и выдача в Благовещенске."
        )
        faq_url = absolute_url(reverse("content:faq"))
        article = build_article_json_ld(
            headline="FAQ по покупке авто из Китая",
            description=context["seo_description"],
            url=faq_url,
            date_published="2024-06-01",
            date_modified="2026-08-01",
        )
        context["article_json_ld"] = serialize_json_ld(article)
        return context
