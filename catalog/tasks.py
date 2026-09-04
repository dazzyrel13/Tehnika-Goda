import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="catalog.sync_avito_price",
    max_retries=3,
    default_retry_delay=15,
)
def sync_avito_price_task(self, vehicle_id: int) -> bool:
    """Push Vehicle.price_rub to the linked Avito listing."""
    from .avito import AvitoAPIError, is_configured, update_item_price
    from .models import Vehicle

    if not is_configured():
        logger.info("Avito sync skipped: credentials not configured")
        return False

    try:
        vehicle = Vehicle.objects.get(pk=vehicle_id)
    except Vehicle.DoesNotExist:
        logger.warning("Avito sync: vehicle %s not found", vehicle_id)
        return False

    if not vehicle.avito_item_id:
        logger.info("Avito sync skipped: vehicle %s has no avito_item_id", vehicle_id)
        return False

    if vehicle.price_rub is None:
        logger.info("Avito sync skipped: vehicle %s has no price_rub", vehicle_id)
        return False

    price = int(vehicle.price_rub)
    try:
        update_item_price(int(vehicle.avito_item_id), price)
    except AvitoAPIError as exc:
        Vehicle.objects.filter(pk=vehicle.pk).update(
            avito_price_sync_error=str(exc)[:255],
        )
        logger.error(
            "Avito sync failed vehicle_id=%s item_id=%s: %s",
            vehicle_id,
            vehicle.avito_item_id,
            exc,
        )
        # Do not retry hard client errors (400/404); retry auth/network/429.
        if exc.status_code in {400, 403, 404}:
            return False
        raise self.retry(exc=exc)

    Vehicle.objects.filter(pk=vehicle.pk).update(
        avito_price_synced_at=timezone.now(),
        avito_price_sync_error="",
    )
    return True
