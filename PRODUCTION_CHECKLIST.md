# Техника Года — Production Checklist

## Security
- Set `DEBUG=False`.
- Set a strong random `SECRET_KEY` (50+ chars).
- Set `USE_HTTPS=True` (required when `DEBUG=False`, unless `ALLOW_INSECURE_PRODUCTION=True` for rare cases).
- If TLS terminates at a reverse proxy, set `BEHIND_HTTPS_PROXY=True` and `TRUST_PROXY_HEADERS=True`.
- Start from `.env.production.example` and replace all placeholders.
- Configure `ALLOWED_HOSTS` with real domain names.
- Configure `CORS_ALLOWED_ORIGINS` with trusted origins only.
- Rotate Telegram bot token if used, and keep it out of VCS.
- Set `REDIS_PASSWORD` and matching `REDIS_BROKER_URL` / `REDIS_CACHE_URL`.
- Set `ADMIN_ALLOWED_IPS` only if you want to restrict admin by office/VPN CIDR (optional).
- Or leave `ADMIN_ALLOWED_IPS` empty and `ALLOW_OPEN_ADMIN=True` — login from any IP; protect with secret `ADMIN_URL_PREFIX`, 2FA, and axes lockout.
- Set a unique `ADMIN_URL_PREFIX` (do not ship the example default). Never reuse a local DEBUG `.env` as the production env file.
- Production `ALLOWED_HOSTS` must be the real domains only (`tehnikagoda.ru`, `www.tehnikagoda.ru`) — no `localhost`.
- After deploy: open the admin URL, sign in, scan the TOTP QR (Google Authenticator / Yandex Ключ) and save backup codes. Admin will not open without 2FA.
- If login is locked after failed attempts: `python manage.py axes_reset`.
- Keep `ANALYTICS_STORE_IP=False` unless you have a documented need for raw IPs.
- After any secret leak (shared `.env`, dumps): rotate `SECRET_KEY`, DB password, Telegram bot token.
- Do not keep `datadump.json` / `*_backup.json` / `db.sqlite3` on the production host.

## Infrastructure
- Configure `DATABASE_URL` for production PostgreSQL.
- Configure `REDIS_BROKER_URL` and `REDIS_CACHE_URL` (with password).
- Run `python manage.py migrate`.
- Run `python manage.py collectstatic --noinput`.
- After deploy, once: `python manage.py generate_image_variants` (card srcset 400/800 for existing photos).
- Ensure logs directory exists and is writable (`logs/`).
- Reload nginx after pulling `nginx/nginx.conf` (gzip, HTTP/2, rate limits on leads/search/login, `/healthz/`, `server_tokens off`, unknown Host on :80 returns 444).
- Schedule DB backups: copy lines from `deploy/crontab.example` (daily `scripts/backup.sh`). Test restore once. Optionally `BACKUP_MEDIA=1`.
- Confirm Celery worker **and** beat are running (`docker compose -f docker-compose.prod.yml ps`).
- Optional: `docker compose -f docker-compose.monitoring.yml up -d` (Uptime Kuma on `:3001`) and monitor `https://tehnikagoda.ru/healthz/`.
- Optional: install `deploy/logrotate-tehnikagoda` and `deploy/fail2ban-sshd.local.example` on the VPS.
- Optional: set `YANDEX_METRIKA_ID` (counter loads only after cookie «Принять»).

## Health Checks
- Run `python manage.py check`.
- Run `python manage.py check --deploy`.
- Run `python manage.py test` / CI coverage (≥65%).
- Verify `GET /healthz/` returns `{"status":"ok","db":true,"redis":true}` (Docker `healthcheck` on `web` uses this).
- Verify admin path and access restrictions.
- Verify lead form rate limits work per client IP (not shared).

## Runtime
- Start app with Gunicorn behind nginx (see `docker-compose.prod.yml`).
- Enforce HTTPS at proxy and app layer.
- Enable monitoring/alerts for app and Celery workers (host metrics + log review).
