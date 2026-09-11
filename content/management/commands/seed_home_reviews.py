"""Seed curated homepage reviews from known public platform posts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from catalog.cache_helpers import invalidate_home_reviews_cache
from content.models import Review

# Upserted by source_url so re-running the command is safe.
HOME_REVIEWS: tuple[dict, ...] = (
    {
        "client_name": "Яна Банщикова",
        "city": "",
        "vehicle_purchased": "",
        "avatar_file": "yana-banshchikova.webp",
        "comment": (
            "Решила заказать автомобиль из Китая и обратилась в компанию Техника Года. "
            "Ребята подробно объяснили нюансы, расписали условия работы. "
            "Видно сразу работают профессионалы. "
            "Машину привезли в срок, по состоянию авто как и обещали — в отличном состоянии. "
            "Весь процесс выбора, заказа и доставки авто очень понятный и простой, "
            "специалисты помогают и объясняют каждый этап. "
            "Езжу уже год — машина 🔥, не подвела ни разу.\n\n"
            "Советую всем — если хотите надежную машину, то вам в Технику Года."
        ),
        "rating": 5,
        "source": Review.SOURCE_YANDEX,
        "source_url": (
            "https://yandex.ru/maps/org/141291293294/reviews"
            "?reviews%5BpublicId%5D=mda6ckbp5czwt55xh365nrp7bw"
            "&si=k5x4xyhf1gueu0fnjkrc7cy0hr&utm_source=review"
        ),
        "date": date(2026, 9, 4),
        "order": 10,
        "is_published": True,
    },
    {
        "client_name": "V K",
        "city": "",
        "vehicle_purchased": "Geely Coolray",
        "avatar_file": "vk-avatar.webp",
        "comment": (
            "Хочу поблагодарить за качественную организацию сделки по импорту "
            "автомобиля Geely Coolray. Процесс подбора, логистики и таможенного "
            "оформления был выполнен на высоком профессиональном уровне. "
            "Спасибо за надежность, ответственный подход к делу и соблюдение "
            "всех договоренностей."
        ),
        "rating": 5,
        "source": Review.SOURCE_2GIS,
        "source_url": "https://2gis.ru/reviews/70000001116002059/review/288215305",
        "date": date(2026, 9, 2),
        "order": 20,
        "is_published": True,
    },
)


class Command(BaseCommand):
    help = "Create or update curated homepage reviews (idempotent by source_url)."

    def handle(self, *args, **options):
        avatar_dir = Path(settings.BASE_DIR) / "data" / "reviews"
        created = 0
        updated = 0
        for payload in HOME_REVIEWS:
            url = payload["source_url"]
            avatar_name = (payload.get("avatar_file") or "").strip()
            defaults = {
                k: v
                for k, v in payload.items()
                if k not in {"source_url", "avatar_file"}
            }
            obj, was_created = Review.objects.update_or_create(
                source_url=url,
                defaults=defaults,
            )
            if avatar_name:
                path = avatar_dir / avatar_name
                if path.exists():
                    with path.open("rb") as fh:
                        obj.avatar.save(path.name, File(fh), save=True)
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Avatar missing: {path}")
                    )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {obj.client_name}"))
            else:
                updated += 1
                self.stdout.write(f"Updated: {obj.client_name}")

        invalidate_home_reviews_cache()
        self.stdout.write(
            self.style.SUCCESS(f"Done. created={created} updated={updated}")
        )
        self._sync_platform_ratings()

    def _sync_platform_ratings(self) -> None:
        """Public platform scores shown on homepage widgets (not local card count)."""
        from decimal import Decimal

        from content.models import ReviewPlatformSettings

        settings_obj = ReviewPlatformSettings.load()
        settings_obj.yandex_rating = Decimal("5.0")
        settings_obj.yandex_count = 7
        settings_obj.twogis_rating = Decimal("5.0")
        settings_obj.twogis_count = 7
        settings_obj.save()
        self.stdout.write(
            self.style.SUCCESS("Platform widgets: Yandex 5.0 · 7, 2GIS 5.0 · 7")
        )
