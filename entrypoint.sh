#!/bin/bash
set -e

mkdir -p /usr/src/app/logs /usr/src/app/staticfiles /usr/src/app/media

if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /usr/src/app/logs /usr/src/app/staticfiles /usr/src/app/media || true
    exec gosu appuser "$0" "$@"
fi

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for PostgreSQL..."

    while ! nc -z "$SQL_HOST" "$SQL_PORT"; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py migrate --noinput
if [[ "$*" == *"gunicorn"* ]]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
