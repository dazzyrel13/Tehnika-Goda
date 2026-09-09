"""Site-wide CNY→RUB rate: manual override beats CBR."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

FALLBACK_CNY_RATE = Decimal("12.48")


def get_effective_cny_rate() -> Decimal:
    from .models import CurrencyRateSettings

    return CurrencyRateSettings.load().effective_rate()


def rub_from_cny(price_cny: Decimal, rate: Decimal | None = None) -> Decimal:
    """Whole rubles, half-up."""
    if rate is None:
        rate = get_effective_cny_rate()
    return (Decimal(price_cny) * Decimal(rate)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )


def apply_currency_pricing(vehicle) -> list[str]:
    """
    Mutate vehicle pricing fields in place.

    - price_cny set → derive price_rub from effective rate
    - only price_rub → leave rubles, mark fixed
    Returns list of field names that were changed (for update_fields merges).
    """
    changed: list[str] = []

    if vehicle.price_cny is not None:
        rate = get_effective_cny_rate()
        new_rub = rub_from_cny(vehicle.price_cny, rate)
        if vehicle.price_rub != new_rub:
            vehicle.price_rub = new_rub
            changed.append("price_rub")
        if vehicle.cny_rate != rate:
            vehicle.cny_rate = rate
            changed.append("cny_rate")
        if vehicle.is_currency_fixed:
            vehicle.is_currency_fixed = False
            changed.append("is_currency_fixed")
        return changed

    if vehicle.price_rub is not None and not vehicle.is_currency_fixed:
        vehicle.is_currency_fixed = True
        changed.append("is_currency_fixed")
    return changed


def recalculate_all_cny_prices() -> int:
    """Re-save every vehicle that has price_cny so RUB tracks the current rate."""
    from .models import Vehicle

    updated = 0
    qs = Vehicle.objects.exclude(price_cny__isnull=True).only(
        "id",
        "price_cny",
        "price_rub",
        "cny_rate",
        "is_currency_fixed",
    )
    for vehicle in qs.iterator(chunk_size=100):
        before = (vehicle.price_rub, vehicle.cny_rate, vehicle.is_currency_fixed)
        apply_currency_pricing(vehicle)
        after = (vehicle.price_rub, vehicle.cny_rate, vehicle.is_currency_fixed)
        if before != after:
            vehicle.save(
                update_fields=["price_rub", "cny_rate", "is_currency_fixed"],
                skip_image_queue=True,
            )
            updated += 1
    return updated
