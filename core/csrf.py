"""CSRF failure logging for production (nginx TLS vs Django HTTP)."""

from __future__ import annotations

import logging

from django.shortcuts import render

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    logger.warning(
        "CSRF rejected method=%s path=%s secure=%s host=%s origin=%s referer=%s reason=%s",
        request.method,
        request.path,
        request.is_secure(),
        request.get_host(),
        request.META.get("HTTP_ORIGIN", ""),
        request.META.get("HTTP_REFERER", ""),
        reason,
    )
    return render(request, "403_csrf.html", status=403)
