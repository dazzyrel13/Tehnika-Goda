import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="leads.send_inquiry_telegram",
    max_retries=3,
    default_retry_delay=10,
)
def send_inquiry_telegram_task(self, inquiry_id: int) -> bool:
    """Deliver lead to Telegram out of band (retries on failure)."""
    from .models import Inquiry
    from .telegram import send_inquiry_notification

    try:
        inquiry = Inquiry.objects.get(pk=inquiry_id)
    except Inquiry.DoesNotExist:
        logger.warning("Telegram task: inquiry %s not found", inquiry_id)
        return False

    ok = send_inquiry_notification(inquiry)
    if not ok:
        raise self.retry()
    return True
