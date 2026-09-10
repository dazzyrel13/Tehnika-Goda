from django.core.management.base import BaseCommand

from catalog.avito_xlsx import (
    AVITO_IMAGE_URLS_KEY,
    enqueue_avito_photo_fetch,
    fetch_avito_photos_for_vehicle,
)
from catalog.models import Vehicle


class Command(BaseCommand):
    help = (
        "Download pending Avito photos for vehicles that store "
        f"specs['{AVITO_IMAGE_URLS_KEY}'] and still need a gallery."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max vehicles to process (0 = all).",
        )
        parser.add_argument(
            "--queue",
            action="store_true",
            help="Enqueue Celery tasks instead of downloading inline.",
        )

    def handle(self, *args, **options):
        pending_ids = []
        for vehicle in Vehicle.objects.only("id", "specs").iterator(chunk_size=100):
            specs = vehicle.specs if isinstance(vehicle.specs, dict) else {}
            if specs.get(AVITO_IMAGE_URLS_KEY):
                pending_ids.append(vehicle.pk)
            if options["limit"] and len(pending_ids) >= options["limit"]:
                break

        self.stdout.write(f"Pending vehicles with Avito photo URLs: {len(pending_ids)}")
        total = 0
        for vehicle_id in pending_ids:
            if options["queue"]:
                enqueue_avito_photo_fetch(vehicle_id)
                self.stdout.write(f"  queued {vehicle_id}")
            else:
                added = fetch_avito_photos_for_vehicle(vehicle_id)
                total += added
                self.stdout.write(f"  vehicle {vehicle_id}: +{added} photos")
        if not options["queue"]:
            self.stdout.write(self.style.SUCCESS(f"Attached photos total: {total}"))
