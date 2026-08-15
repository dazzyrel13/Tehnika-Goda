# Short ops notes (RF / free stack). Details also in PRODUCTION_CHECKLIST.md and README.

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
