"""SEO landing: автомобили под заказ из Китая + общий прайс."""

from __future__ import annotations

from django.utils import timezone

from core.info_pages import InfoPageView
from utils.seo import absolute_url, build_faq_page_json_ld, serialize_json_ld

from .price_list import grouped_price_list

AVTO_POD_ZAKAZ_FAQS: list[tuple[str, str]] = [
    (
        "Что значит автомобиль под заказ из Китая?",
        "Мы подбираем модель на площадке и у дилеров в Китае, проверяем до оплаты, "
        "оформляем ввоз и документы на ваше имя. Это не витрина салона РФ: машина "
        "приезжает под ваш запрос с ориентировочной ценой из прайса.",
    ),
    (
        "Цены в прайсе финальные?",
        "Нет. В таблице — ориентир «от» на дату обновления. Итог зависит от комплектации, "
        "года, пробега, курса и пакета документов. Точную сумму фиксируем в договоре "
        "до оплаты.",
    ),
    (
        "Можно купить китайский авто с доставкой в Москву и другие города?",
        "Да. Работаем с клиентами по всей России: после оформления организуем доставку "
        "автовозом в ваш город — Москву, Санкт-Петербург, регионы.",
    ),
    (
        "BMW, Audi, Toyota из Китая — это новые или с пробегом?",
        "В прайсе встречаются и новые, и с небольшим пробегом (китайский рынок). "
        "По каждой модели уточняем статус, комплектацию и историю до сделки.",
    ),
    (
        "Что входит в цену под заказ?",
        "Обычно автомобиль, логистика по Китаю, таможня и пакет документов (ЭПТС и сопутствующее). "
        "Автовоз по России и отдельные опции считаются отдельно.",
    ),
    (
        "Сколько занимает привоз автомобиля из Китая?",
        "Ориентир — до нескольких недель с момента оплаты инвойса; точный срок зависит "
        "от модели, очереди на таможне и логистики. Согласуем график в договоре.",
    ),
    (
        "Чем заказ из Китая отличается от покупки в российском салоне?",
        "Другая цена и комплектации с китайского рынка, прямая проверка до оплаты и "
        "сопровождение ввоза. Вы получаете прозрачный расчёт под конкретный автомобиль, "
        "а не «ценник витрины».",
    ),
    (
        "Есть ли гарантия?",
        "На автомобили с нашей площадки действует гарантия 6 месяцев на ДВС и КПП. "
        "Условия по конкретной машине подтверждаем при оформлении.",
    ),
]


class AvtoPodZakazView(InfoPageView):
    page_key = "avto_pod_zakaz"
    template_name = "info/avto_pod_zakaz.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups = grouped_price_list(active_only=True)
        context["price_groups"] = groups
        context["price_brand_nav"] = [
            {"brand": g["brand"], "anchor": g["anchor"]} for g in groups
        ]
        updated = None
        for group in groups:
            for item in group["items"]:
                ts = item.updated_at
                if updated is None or ts > updated:
                    updated = ts
        context["price_updated_at"] = updated or timezone.now()

        page_url = absolute_url(self.request.path)
        faq_ld = build_faq_page_json_ld(faqs=AVTO_POD_ZAKAZ_FAQS, page_url=page_url)
        context["faqs"] = AVTO_POD_ZAKAZ_FAQS
        context["faq_json_ld"] = serialize_json_ld(faq_ld)
        return context
