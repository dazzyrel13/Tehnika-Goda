"""
One-off local seed for categories / sample linkage.
Not used in Docker images (.dockerignore). Do not run on production data.
"""

from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

import django
from django.contrib.auth.models import User

from catalog.models import Brand, Category, Vehicle

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

PASSWORD_FILE = Path(__file__).resolve().parent / ".seed_admin_password"


def seed_database():
    print("--- Техника Года: заполнение справочников ---")

    user_qs = User.objects.filter(username="admin")
    if not user_qs.exists():
        random_password = uuid.uuid4().hex[:16]
        User.objects.create_superuser(
            "admin", "admin@tehnikagoda.local", random_password
        )
        PASSWORD_FILE.write_text(random_password + "\n", encoding="utf-8")
        try:
            PASSWORD_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        print(
            f"Admin created (username=admin). Password written to {PASSWORD_FILE.name} — "
            "save it, then delete the file."
        )
    else:
        print("Admin user already exists. Skipping password reset for security.")

    print("Создаём категории каталога...")

    cat_cars, _ = Category.objects.get_or_create(
        name="Легковые автомобили", slug="cars"
    )
    cat_trucks, _ = Category.objects.get_or_create(
        name="Грузовой транспорт", slug="trucks"
    )
    cat_special, _ = Category.objects.get_or_create(name="Спецтехника", slug="special")

    Category.objects.get_or_create(name="Новые", slug="cars_new", parent=cat_cars)
    Category.objects.get_or_create(name="С пробегом", slug="cars_used", parent=cat_cars)
    Category.objects.get_or_create(
        name="Выкупленные", slug="cars_bought", parent=cat_cars
    )
    Category.objects.get_or_create(name="Седаны", slug="cars_sedan", parent=cat_cars)
    Category.objects.get_or_create(
        name="Кроссоверы", slug="cars_crossover", parent=cat_cars
    )
    Category.objects.get_or_create(name="Внедорожники", slug="cars_suv", parent=cat_cars)
    Category.objects.get_or_create(name="Минивэны", slug="cars_minivan", parent=cat_cars)

    Category.objects.get_or_create(
        name="Грузовики", slug="trucks_trucks", parent=cat_trucks
    )
    Category.objects.get_or_create(name="Фургоны", slug="trucks_vans", parent=cat_trucks)
    Category.objects.get_or_create(
        name="Бортовые с КМУ", slug="trucks_km", parent=cat_trucks
    )
    Category.objects.get_or_create(
        name="Эвакуаторы", slug="trucks_evac", parent=cat_trucks
    )

    Category.objects.get_or_create(
        name="Автовышки", slug="special_lifts", parent=cat_special
    )
    Category.objects.get_or_create(
        name="Башенные краны", slug="special_cranes", parent=cat_special
    )

    Brand.objects.get_or_create(name="Xiaomi", slug="xiaomi")
    Brand.objects.get_or_create(name="Zeekr", slug="zeekr")
    Brand.objects.get_or_create(name="BYD", slug="byd")

    Vehicle.objects.filter(slug="xiaomi-su7-ultra").update(
        category=Category.objects.filter(slug="cars_new").first()
    )
    Vehicle.objects.filter(slug="zeekr-001-fr").update(
        category=Category.objects.filter(slug="cars_new").first()
    )
    Vehicle.objects.filter(slug="yangwang-u9").update(
        category=Category.objects.filter(slug="cars_new").first()
    )

    print("Elite hierarchy seed complete.")


if __name__ == "__main__":
    seed_database()
