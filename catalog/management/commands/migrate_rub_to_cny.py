from django.core.management.base import BaseCommand

from catalog.cache_helpers import invalidate_vehicle_public_caches
from catalog.currency import FALLBACK_CNY_RATE, migrate_legacy_rub_to_cny
from catalog.models import CurrencyRateSettings, Vehicle


class Command(BaseCommand):
    help = (
        "Fill price_cny for RUB-only vehicles as rub / 12.48, "
        "then recalculate RUB from the site effective CNY rate."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only count how many vehicles would be converted.",
        )

    def handle(self, *args, **options):
        pending = (
            Vehicle.objects.filter(price_cny__isnull=True, price_rub__isnull=False)
            .exclude(price_rub=0)
            .count()
        )
        settings = CurrencyRateSettings.load()
        self.stdout.write(
            f"Pending RUB→CNY (÷{FALLBACK_CNY_RATE}): {pending}. "
            f"Effective rate now: {settings.effective_rate()} "
            f"({settings.rate_source_label()})."
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes."))
            return

        result = migrate_legacy_rub_to_cny()
        invalidate_vehicle_public_caches()
        self.stdout.write(
            self.style.SUCCESS(
                f"Converted: {result['converted']}. "
                f"Recalculated: {result['recalculated']}."
            )
        )
