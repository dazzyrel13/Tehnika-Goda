#!/usr/bin/env bash
# Backup Postgres (+ optional media) for Docker Compose stacks.
# Usage:
#   ./scripts/backup.sh
#   COMPOSE_FILE=docker-compose.prod.yml DB_CONTAINER=tehnikagoda_db ./scripts/backup.sh
#   BACKUP_MEDIA=1 ./scripts/backup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DB_CONTAINER="${DB_CONTAINER:-tehnikagoda_db}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$OUT_DIR"

POSTGRES_DB="$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB)"
POSTGRES_USER="$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER)"

DUMP="$OUT_DIR/pg_${POSTGRES_DB}_${STAMP}.sql.gz"
echo "Dumping $POSTGRES_DB from $DB_CONTAINER → $DUMP"
docker exec "$DB_CONTAINER" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl \
  | gzip -c > "$DUMP"

if [[ "${BACKUP_MEDIA:-0}" == "1" ]]; then
  MEDIA_TGZ="$OUT_DIR/media_${STAMP}.tar.gz"
  echo "Archiving media → $MEDIA_TGZ"
  if [[ -d "$ROOT/media" ]] && [[ -n "$(ls -A "$ROOT/media" 2>/dev/null || true)" ]]; then
    tar -czf "$MEDIA_TGZ" -C "$ROOT" media
  else
    WEB_CONTAINER="${WEB_CONTAINER:-tehnikagoda_web}"
    docker run --rm --volumes-from "$WEB_CONTAINER" -v "$OUT_DIR:/backup" alpine:3.20 \
      tar -czf "/backup/media_${STAMP}.tar.gz" -C /usr/src/app media
  fi
fi

find "$OUT_DIR" -type f \( -name 'pg_*.sql.gz' -o -name 'media_*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true

echo "Done. Restore example:"
echo "  gunzip -c \"$DUMP\" | docker exec -i $DB_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB"
