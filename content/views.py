from django.views.generic import TemplateView

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
        return context
