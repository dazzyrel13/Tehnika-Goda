from django.core.management.base import BaseCommand, CommandError

from catalog.avito_xlsx import import_avito_xlsx
from catalog.cache_helpers import invalidate_vehicle_public_caches


class Command(BaseCommand):
    help = (
        "Import Avito autoload .xlsx into unpublished vehicle drafts. "
        "Skips rows that already exist (AvitoId or title/year/mileage/color)."
    )

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Path to Avito .xlsx file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report only; do not create vehicles.",
        )
        parser.add_argument(
            "--no-photos",
            action="store_true",
            help="Do not download ImageUrls.",
        )

    def handle(self, *args, **options):
        path = options["xlsx_path"]
        try:
            report = import_avito_xlsx(
                path,
                dry_run=options["dry_run"],
                download_photos=not options["no_photos"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(report.summary())
        for line in report.linked_reasons[:30]:
            self.stdout.write(self.style.SUCCESS(f"  link: {line}"))
        if len(report.linked_reasons) > 30:
            self.stdout.write(f"  … и ещё {len(report.linked_reasons) - 30} привязок")
        for line in report.skipped_reasons[:30]:
            self.stdout.write(f"  skip: {line}")
        if len(report.skipped_reasons) > 30:
            self.stdout.write(f"  … и ещё {len(report.skipped_reasons) - 30}")
        for line in report.warnings[:30]:
            self.stdout.write(self.style.WARNING(f"  warn: {line}"))
        for line in report.errors:
            self.stdout.write(self.style.ERROR(f"  error: {line}"))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — ничего не создано."))
            return

        if report.created or report.linked:
            invalidate_vehicle_public_caches()
        if report.created:
            self.stdout.write(
                self.style.SUCCESS(f"Созданы id: {report.created_ids}")
            )
        if report.linked:
            self.stdout.write(
                self.style.SUCCESS(f"Привязан Avito ID к: {report.linked_ids}")
            )
