import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def enqueue_process_vehicle_main_image(vehicle_id: int) -> None:
    """Queue WebP/variants for a vehicle cover; fall back to sync if broker is down."""
    try:
        process_vehicle_main_image_task.delay(vehicle_id)
    except Exception:
        logger.exception(
            "Image queue failed for vehicle %s; processing inline", vehicle_id
        )
        process_vehicle_main_image_task(vehicle_id)


def enqueue_process_gallery_image(image_id: int) -> None:
    try:
        process_gallery_image_task.delay(image_id)
    except Exception:
        logger.exception(
            "Image queue failed for gallery %s; processing inline", image_id
        )
        process_gallery_image_task(image_id)


def _finalize_image_field(instance, field_name: str) -> None:
    """Convert master to WebP if needed, then write .w400/.w800 variants."""
    from utils.image_processing import (
        process_image_to_webp,
        should_process_image,
        write_responsive_variants,
    )

    field = getattr(instance, field_name, None)
    if not field or not getattr(field, "name", None):
        return

    if should_process_image(field):
        processed = process_image_to_webp(field)
        if processed:
            setattr(instance, field_name, processed)
            instance.save(update_fields=[field_name], skip_image_queue=True)
            return

    write_responsive_variants(field)


@shared_task(
    name="catalog.process_vehicle_main_image",
    ignore_result=True,
    max_retries=2,
    default_retry_delay=15,
)
def process_vehicle_main_image_task(vehicle_id: int) -> None:
    from .models import Vehicle

    try:
        vehicle = Vehicle.objects.get(pk=vehicle_id)
    except Vehicle.DoesNotExist:
        logger.warning("Image process: vehicle %s not found", vehicle_id)
        return
    _finalize_image_field(vehicle, "main_image")


@shared_task(
    name="catalog.process_gallery_image",
    ignore_result=True,
    max_retries=2,
    default_retry_delay=15,
)
def process_gallery_image_task(image_id: int) -> None:
    from .models import VehicleImage

    try:
        item = VehicleImage.objects.get(pk=image_id)
    except VehicleImage.DoesNotExist:
        logger.warning("Image process: gallery image %s not found", image_id)
        return
    _finalize_image_field(item, "image")


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
