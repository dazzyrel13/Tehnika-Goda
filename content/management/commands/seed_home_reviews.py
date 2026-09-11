"""Seed curated homepage reviews from known public platform posts."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from catalog.cache_helpers import invalidate_home_reviews_cache
from content.models import Review

# Upserted by source_url so re-running the command is safe.
HOME_REVIEWS: tuple[dict, ...] = (
    {
        "client_name": "Яна Банщикова",
        "city": "",
        "vehicle_purchased": "",
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
)


class Command(BaseCommand):
    help = "Create or update curated homepage reviews (idempotent by source_url)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for payload in HOME_REVIEWS:
            url = payload["source_url"]
            defaults = {k: v for k, v in payload.items() if k != "source_url"}
            obj, was_created = Review.objects.update_or_create(
                source_url=url,
                defaults=defaults,
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
