from django.core.management.base import BaseCommand

from catalog.models import Vehicle, VehicleImage
from utils.image_processing import process_image_to_webp, write_responsive_variants


class Command(BaseCommand):
    help = (
        "Downscale oversized WebP masters (no recompress of already-small files) "
        "and write .w400 / .w800 variants for catalog photos."
    )

    def handle(self, *args, **options):
        processed = 0
        variants = 0

        vehicles = Vehicle.objects.exclude(main_image="").exclude(main_image=None)
        total = vehicles.count()
        for i, vehicle in enumerate(vehicles.iterator(), start=1):
            if self._refresh_field(vehicle, "main_image"):
                processed += 1
            if vehicle.main_image:
                write_responsive_variants(vehicle.main_image)
                variants += 1
            if i % 25 == 0:
                self.stdout.write(f"vehicles {i}/{total}")

        gallery = VehicleImage.objects.exclude(image="").exclude(image=None)
        gtotal = gallery.count()
        for i, item in enumerate(gallery.iterator(), start=1):
            if self._refresh_field(item, "image"):
                processed += 1
            if item.image:
                write_responsive_variants(item.image)
                variants += 1
            if i % 50 == 0:
                self.stdout.write(f"gallery {i}/{gtotal}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. resized_or_converted={processed} variants_written={variants}"
            )
        )

    @staticmethod
    def _refresh_field(obj, field_name: str) -> bool:
        field = getattr(obj, field_name)
        processed = process_image_to_webp(field)
        if not processed:
            return False
        field.save(processed.name, processed, save=False)
        obj.save(update_fields=[field_name])
        return True
