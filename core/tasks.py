import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="core.send_admin_login_approval_email",
    max_retries=2,
    default_retry_delay=15,
)
def send_admin_login_approval_email_task(
    self,
    *,
    session_key: str,
    user_id: int,
    approve_url: str,
    client_ip: str,
) -> bool:
    """Send admin login approval email without blocking the login HTTP request."""
    recipient = (getattr(settings, "ADMIN_LOGIN_APPROVAL_EMAIL", "") or "").strip()
    if not recipient:
        logger.error("ADMIN_LOGIN_APPROVAL_EMAIL is not configured")
        return False

    user = get_user_model().objects.filter(pk=user_id).first()
    username = user.get_username() if user else f"user#{user_id}"

    subject = f"Техника Года — подтвердите вход ({username})"
    message = (
        f"Запрос входа в админку.\n\n"
        f"Пользователь: {username}\n"
        f"IP: {client_ip or 'unknown'}\n\n"
        f"Подтвердить вход (действует 20 мин):\n{approve_url}\n\n"
        f"Если это не вы — просто проигнорируйте письмо."
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.exception("Failed to send admin login approval email")
        raise self.retry(exc=exc) from exc


@shared_task(
    bind=True,
    name="core.send_admin_login_approval_telegram",
    max_retries=2,
    default_retry_delay=10,
)
def send_admin_login_approval_telegram_task(
    self,
    *,
    session_key: str,
    user_id: int,
    approve_url: str,
    client_ip: str,
) -> bool:
    from leads.telegram import send_admin_login_approval

    user = get_user_model().objects.filter(pk=user_id).first()
    username = user.get_username() if user else f"user#{user_id}"

    ok = send_admin_login_approval(
        approve_url=approve_url,
        username=username,
        client_ip=client_ip,
    )
    if not ok:
        raise self.retry()
    return True
