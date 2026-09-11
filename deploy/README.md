# Short ops notes (RF / free stack). Details also in PRODUCTION_CHECKLIST.md and README.

## Host nginx (Timeweb VPS)
```bash
sudo cp /etc/nginx/sites-available/tehnikagoda.ru /etc/nginx/sites-available/tehnikagoda.ru.bak
sudo cp nginx/tehnikagoda.http.conf /etc/nginx/conf.d/tehnikagoda.http.conf
sudo cp nginx/tehnikagoda.ru.host.conf /etc/nginx/sites-available/tehnikagoda.ru
sudo nginx -t && sudo systemctl reload nginx
```
If cert paths differ, edit the `ssl_certificate*` lines before reload.

## Uptime Kuma
```bash
docker compose -f docker-compose.monitoring.yml up -d
```
Open http://127.0.0.1:3001 — create user — add HTTP monitor to `/healthz/`.
Telegram notifications can be added later in Kuma → Settings → Notifications.

## Backups
```bash
# once
./scripts/backup.sh
# schedule: see deploy/crontab.example
```

## Logrotate
```bash
sudo cp deploy/logrotate-tehnikagoda /etc/logrotate.d/tehnikagoda
```

## SSH hardening (optional)
```bash
sudo apt install fail2ban
sudo cp deploy/fail2ban-sshd.local.example /etc/fail2ban/jail.d/sshd.local
sudo systemctl enable --now fail2ban
```

## Yandex Metrika
Set `YANDEX_METRIKA_ID` in `.env` (counter number only). Loads only after cookie «Принять».
