# Техника Года

Каталог автомобилей и спецтехники из Китая (`tehnikagoda.ru`): серверный Django-сайт, заявки в Telegram, аналитика визитов.

## Стек

- Python 3.11, Django 5.2
- PostgreSQL 15 + Redis (прод / Docker)
- Celery + Beat (очистка аналитики)
- Gunicorn, Nginx, WhiteNoise

## Быстрый старт (Docker)

```bash
cp .env.example .env
# задайте SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD

make up
# или: docker compose -f docker-compose.dev.yml up --build
```

Сайт: http://localhost:8000  
Health: http://localhost:8000/healthz/  
Админка: http://localhost:8000/<ADMIN_URL_PREFIX>/  
(значение `ADMIN_URL_PREFIX` из `.env` — в проде задайте уникальный префикс)

Вход в админку: пароль + одноразовый код из приложения-аутентификатора. Если логин заблокирован: `python manage.py axes_reset`.

В dev-стеке: `web` (runserver), `db`, `redis`, `celery_worker`.

Полезные команды: `make help` (`test`, `coverage`, `backup`, `health`, `seed`, `monitor`).

Опциональный мониторинг (Uptime Kuma, бесплатно, РФ): `make monitor` → http://127.0.0.1:3001 — см. `deploy/README.md`.

## Локально без Docker

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Для фоновых задач нужны Redis и:

```bash
celery -A core worker -l INFO
celery -A core beat -l INFO
```

## Прод

См. `.env.production.example`, `docker-compose.prod.yml`, `PRODUCTION_CHECKLIST.md`, `nginx/nginx.conf`.

Не используйте локальный `.env` как прод-конфиг: держите отдельные файлы (`.env.example` → local, `.env.production.example` → prod).

```bash
docker compose -f docker-compose.prod.yml up --build -d
python manage.py check --deploy
python manage.py test
```

`docker-compose.yml` без суффикса — только Postgres + Redis (infra). Полный стек: `.dev.yml` / `.prod.yml`.

Бэкапы: `make backup` / `./scripts/backup.sh` (Linux) или `.\scripts\backup.ps1` (Windows). Каталог `backups/` в `.gitignore`. Расписание на VPS: `deploy/crontab.example`.

Операционка (logrotate, fail2ban, Kuma): `deploy/README.md`.

## Тесты

```bash
make test
make coverage   # fail_under=65 (см. .coveragerc)
# или:
docker exec tehnikagoda_web_dev python manage.py test
```

## Приложения

| App | Назначение |
|-----|------------|
| `catalog` | Каталог, фильтры, парсер URL |
| `leads` | Заявки → Telegram |
| `analytics` | Визиты, ретеншн |
| `content` | FAQ (статический текст), отзывы (`Review`) |
| `utils` | WebP, санитизация HTML, SSRF-safe HTTP |

## Переменные окружения

Обязательные: `SECRET_KEY`, `REDIS_PASSWORD` (Docker).  
Опциональные: `TELEGRAM_*`, `YANDEX_METRIKA_ID`, `ANALYTICS_ASYNC`, `ANALYTICS_RETENTION_DAYS`, `ADMIN_ALLOWED_IPS`.
