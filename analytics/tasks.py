import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import VisitEvent

logger = logging.getLogger(__name__)


def persist_visit_event(payload: dict) -> None:
    """Create a VisitEvent from a serializable payload dict."""
    VisitEvent.objects.create(
        visitor_id=payload.get("visitor_id", ""),
        session_key=payload.get("session_key", ""),
        ip_address=payload.get("ip_address"),
        user_agent=payload.get("user_agent", ""),
        path=payload.get("path", ""),
        referer=payload.get("referer", ""),
        utm_source=payload.get("utm_source", ""),
        utm_medium=payload.get("utm_medium", ""),
        utm_campaign=payload.get("utm_campaign", ""),
        vehicle_id=payload.get("vehicle_id"),
        is_vehicle_page=bool(payload.get("is_vehicle_page", False)),
    )


@shared_task(name="analytics.record_visit_event_task")
def record_visit_event_task(payload: dict):
    persist_visit_event(payload)
    return "ok"


@shared_task(name="analytics.cleanup_old_visit_events_task")
def cleanup_old_visit_events_task():
    days = int(getattr(settings, "ANALYTICS_RETENTION_DAYS", 90))
    if days < 1:
        logger.warning("Analytics retention skipped: ANALYTICS_RETENTION_DAYS < 1")
        return 0
    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = VisitEvent.objects.filter(created_at__lt=cutoff).delete()
    logger.info("Deleted %s visit events older than %s days", deleted, days)
    return deleted
