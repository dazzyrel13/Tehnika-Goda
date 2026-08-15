"""Liveness/readiness probe: database + Redis cache."""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def _check_db() -> bool:
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        logger.exception("healthz: database check failed")
        return False


def _check_redis() -> bool:
    try:
        cache.set("healthz:ping", "1", timeout=5)
        return cache.get("healthz:ping") == "1"
    except Exception:
        logger.exception("healthz: redis/cache check failed")
        return False


@never_cache
@require_GET
def healthz(request):
    """
    Returns 200 when DB and Redis are reachable, otherwise 503.
    Safe for load balancers — no secrets, no auth.
    """
    checks = {
        "db": _check_db(),
        "redis": _check_redis(),
    }
    ok = all(checks.values())
    payload = {
        "status": "ok" if ok else "unhealthy",
        **checks,
    }
    return JsonResponse(payload, status=200 if ok else 503)
