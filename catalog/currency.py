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


def cny_from_rub(price_rub: Decimal, rate: Decimal | None = None) -> Decimal:
    """Yuan with 2 decimal places, half-up. Default rate is legacy 12.48."""
    if rate is None:
        rate = FALLBACK_CNY_RATE
    return (Decimal(price_rub) / Decimal(rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def migrate_legacy_rub_to_cny(
    *,
    legacy_rate: Decimal | None = None,
) -> dict[str, int]:
    """
    Fill price_cny for RUB-only vehicles as rub / legacy_rate (default 12.48),
    then recalculate price_rub from the site effective rate.
    """
    from .models import Vehicle

    if legacy_rate is None:
        legacy_rate = FALLBACK_CNY_RATE

    converted = 0
    qs = (
        Vehicle.objects.filter(price_cny__isnull=True, price_rub__isnull=False)
        .exclude(price_rub=0)
        .only("id", "price_cny", "price_rub", "cny_rate", "is_currency_fixed")
    )
    for vehicle in qs.iterator(chunk_size=100):
        vehicle.price_cny = cny_from_rub(vehicle.price_rub, legacy_rate)
        apply_currency_pricing(vehicle)
        vehicle.save(
            update_fields=[
                "price_cny",
                "price_rub",
                "cny_rate",
                "is_currency_fixed",
            ],
            skip_image_queue=True,
        )
        converted += 1

    # Refresh cars that already had CNY (rate may have changed).
    refreshed = recalculate_all_cny_prices()
    return {"converted": converted, "recalculated": refreshed}


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
