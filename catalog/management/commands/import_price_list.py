from django.core.management.base import BaseCommand, CommandError

from catalog.price_list import import_price_list


class Command(BaseCommand):
    help = (
        "Import the public «авто под заказ» price matrix from Excel (.xlsx/.xls). "
        "Duplicates by title keep the minimum price."
    )

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Path to price list Excel file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse only; do not write to the database.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Deactivate positions missing from the file.",
        )

    def handle(self, *args, **options):
        path = options["xlsx_path"]
        try:
            report = import_price_list(
                path,
                replace=options["replace"],
                dry_run=options["dry_run"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(report.summary())
        for line in report.errors:
            self.stdout.write(self.style.ERROR(f"  error: {line}"))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — ничего не сохранено."))
            return
        self.stdout.write(self.style.SUCCESS("Прайс обновлён."))
