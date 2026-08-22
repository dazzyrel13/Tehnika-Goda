"""SEO copy for catalog category / brand listing pages."""

from __future__ import annotations

# Keys: category slug → (h1, intro paragraph)
CATEGORY_SEO: dict[str, tuple[str, str]] = {
    "cars": (
        "Автомобили под заказ из Китая",
        "Автомобили под заказ из Китая с собственной площадки: проверка до оплаты, "
        "прозрачный расчёт и цена под ключ до выдачи в Благовещенске.",
    ),
    "cars_sedan": (
        "Седаны из Китая",
        "Седаны с площадки в Китае — актуальные комплектации, проверка до выкупа "
        "и сопровождение до выдачи в Благовещенске.",
    ),
    "cars_crossover": (
        "Кроссоверы из Китая",
        "Кроссоверы и городские SUV из Китая: подбор под бюджет, диагностика до оплаты "
        "и расчёт под ключ до Благовещенска.",
    ),
    "cars_suv": (
        "Внедорожники из Китая",
        "Внедорожники с площадки в Китае — проверка до выкупа, понятная структура цены "
        "и расчёт под ключ до выдачи в Благовещенске.",
    ),
    "cars_minivan": (
        "Минивэны из Китая",
        "Семейные и коммерческие минивэны из Китая: подбор, проверка до оплаты "
        "и цена под ключ до Благовещенска.",
    ),
    "cars_new": (
        "Новые автомобили",
        "Новые легковые автомобили с площадки в Китае, в том числе с небольшим "
        "техническим пробегом. Подбор, проверка до оплаты и расчёт под ключ "
        "до выдачи в Благовещенске.",
    ),
    "cars_bought": (
        "Выкупленные автомобили",
        "Выкупленные автомобили с собственной площадки в Китае. "
        "Проверка до оплаты и расчёт под ключ до выдачи в Благовещенске.",
    ),
    "cars_used": (
        "Автомобили с пробегом из Китая",
        "Легковые автомобили с пробегом с площадки в Китае: диагностика до оплаты "
        "и прозрачный расчёт до Благовещенска.",
    ),
    "trucks": (
        "Коммерческий транспорт из Китая",
        "Грузовики, фургоны и спецтранспорт для бизнеса: подбор под задачу, "
        "проверка до оплаты и цена под ключ до Благовещенска.",
    ),
    "trucks_trucks": (
        "Грузовики из Китая",
        "Грузовые автомобили с площадки в Китае — подбор под объём и маршрут, "
        "проверка до оплаты и расчёт под ключ.",
    ),
    "trucks_vans": (
        "Фургоны из Китая",
        "Цельнометаллические и грузовые фургоны из Китая для бизнеса: "
        "проверка до выкупа и цена под ключ до Благовещенска.",
    ),
    "trucks_km": (
        "Бортовые с КМУ из Китая",
        "Бортовые автомобили с краном-манипулятором: подбор конфигурации, "
        "проверка до оплаты и расчёт под ключ.",
    ),
    "trucks_evac": (
        "Эвакуаторы из Китая",
        "Эвакуаторы с площадки в Китае для автосервиса и логистики: "
        "проверка до оплаты и цена под ключ до Благовещенска.",
    ),
    "special": (
        "Спецтехника из Китая",
        "Автовышки и башенные краны: подбор под объект, "
        "проверка до оплаты и расчёт под ключ до Благовещенска.",
    ),
    "special_lifts": (
        "Автовышки из Китая",
        "Автовышки для строительства и обслуживания: подбор высоты и шасси, "
        "проверка до оплаты и цена под ключ.",
    ),
    "special_cranes": (
        "Башенные краны из Китая",
        "Башенные краны с площадки в Китае: подбор под объект, "
        "проверка до оплаты и расчёт под ключ до Благовещенска.",
    ),
}

_FILTER_PARAM_KEYS = frozenset(
    {
        "year_from",
        "year_to",
        "price_from",
        "price_to",
        "mileage_to",
        "color",
        "transmission",
        "engine_type",
        "q",
        "body_type",
        "brand",
        "category",
        "page",
    }
)


def category_heading(slug: str, fallback_name: str = "") -> tuple[str, str]:
    """Return (h1, intro) for a category slug."""
    if slug in CATEGORY_SEO:
        return CATEGORY_SEO[slug]
    name = fallback_name or slug
    return (
        f"{name} из Китая",
        f"Каталог «{name}» с площадки в Китае: актуальные предложения, "
        "проверка до оплаты и цена под ключ до выдачи в Благовещенске.",
    )


def brand_heading(brand_name: str) -> tuple[str, str]:
    return (
        f"{brand_name} из Китая",
        f"Автомобили {brand_name} с площадки в Китае: проверка до оплаты "
        "и расчёт под ключ до выдачи в Благовещенске.",
    )


def brand_meta_description(brand_name: str) -> str:
    return (
        f"{brand_name} под заказ из Китая — подбор, фото и видео с площадки, "
        "бесплатный просчёт и цена под ключ до Благовещенска. Техника Года."
    )


def model_meta_description(brand_name: str, model_name: str) -> str:
    full = f"{brand_name} {model_name}".strip()
    return (
        f"{full} под заказ из Китая — подбор комплектации, проверка до оплаты "
        "и расчёт под ключ до Благовещенска. Техника Года."
    )


def model_heading(brand_name: str, model_name: str) -> tuple[str, str]:
    full = f"{brand_name} {model_name}".strip()
    return (
        f"{full} из Китая",
        f"{full} под заказ с площадки в Китае: подбор комплектации, проверка до оплаты "
        "и расчёт под ключ до выдачи в Благовещенске.",
    )


_EMPTY_CALLOUT_PERKS: tuple[str, ...] = (
    "Бесплатный просчёт под ваш запрос",
    "Фото и видео с площадки до оплаты",
    "Итоговая цена под ключ до Благовещенска",
)


def brand_empty_callout(brand_name: str) -> dict:
    return {
        "title": f"{brand_name} пока не в каталоге",
        "text": (
            f"Готовые объявления {brand_name} мы ещё не опубликовали — каталог пополняется "
            "каждый день. Но отсутствие карточки на сайте не значит, что нужный автомобиль "
            "недоступен. Помимо собственной площадки в Китае, мы также работаем с дилерами — "
            "поэтому можем привезти любой интересующий вас автомобиль."
        ),
        "perks": _EMPTY_CALLOUT_PERKS,
        "cta_label": "Получить бесплатный просчёт",
        "lead_prefill": f"Интересует {brand_name} под заказ из Китая.",
    }


def model_empty_callout(brand_name: str, model_name: str) -> dict:
    full = f"{brand_name} {model_name}".strip()
    return {
        "title": f"Готовых предложений по {full} пока нет",
        "text": (
            f"Готовые объявления по {full} мы ещё не опубликовали — каталог пополняется "
            "каждый день. Но отсутствие карточки на сайте не значит, что нужный автомобиль "
            "недоступен. Помимо собственной площадки в Китае, мы также работаем с дилерами — "
            "поэтому можем привезти любой интересующий вас автомобиль."
        ),
        "perks": _EMPTY_CALLOUT_PERKS,
        "cta_label": f"Заказать {full}",
        "lead_prefill": f"Интересует {full} под заказ из Китая.",
    }


def model_empty_intro(brand_name: str, model_name: str) -> str:
    """Backward-compatible single paragraph (tests / short contexts)."""
    return model_empty_callout(brand_name, model_name)["text"]


def has_extra_listing_filters(get_params, *, path_has_category: bool, path_has_brand: bool) -> bool:
    """
    True when the listing is a filtered / paginated variant that should not be indexed.
    Clean single category or brand routes stay indexable.
    """
    params = {k: v for k, v in get_params.items() if str(v).strip()}
    page = params.get("page", "1")
    if page not in ("", "1"):
        return True

    # Dual dimension: category path + brand query (or both in query).
    has_brand = bool(params.get("brand")) or path_has_brand
    has_category = bool(params.get("category")) or path_has_category
    if has_brand and has_category:
        return True

    facet_keys = _FILTER_PARAM_KEYS - {"category", "brand", "page"}
    if any(params.get(k) for k in facet_keys):
        return True

    return False
