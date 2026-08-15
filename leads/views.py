import logging
import time
from datetime import timedelta

from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django_ratelimit.decorators import ratelimit

from .forms import InquiryForm
from .models import Inquiry
from .telegram import send_inquiry_notification

logger = logging.getLogger(__name__)

SUCCESS_MESSAGE = (
    "Заявка успешно отправлена! Свяжемся в течение 15 минут в рабочее время."
)
# Soft-fail bots. Missing form_ts = no-JS human (allow).
# Stamp is set on first form interaction, not page load — fast fillers are OK.
MIN_FORM_SECONDS = 0.6
MAX_FORM_SECONDS = 60 * 60 * 12
CLOCK_SKEW_SECONDS = 300
COOLDOWN_SECONDS = 600


def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _safe_redirect(request, fallback="catalog:index"):
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        url=referer, allowed_hosts={request.get_host()}
    ):
        return redirect(referer)
    return redirect(fallback)


def _pick_utm(request, key, max_len):
    """Prefer POST (form hidden fields), then session."""
    raw = (request.POST.get(key) or request.session.get(key) or "").strip()
    return raw[:max_len]


def _fake_success(request):
    if _is_ajax(request):
        return JsonResponse({"status": "success", "message": SUCCESS_MESSAGE})
    messages.success(request, SUCCESS_MESSAGE)
    return redirect("catalog:index")


def _cooldown_response(request, message: str):
    if _is_ajax(request):
        return JsonResponse(
            {"status": "error", "errors": {"__all__": [message]}},
            status=429,
        )
    messages.error(request, message)
    return _safe_redirect(request)


def _is_bot_timing(request) -> bool:
    """Reject instant / stale posts. Missing timestamp = allow (no-JS)."""
    raw = (request.POST.get("form_ts") or "").strip()
    if not raw:
        return False
    try:
        started = float(raw)
    except (TypeError, ValueError):
        return True
    elapsed = time.time() - started
    if elapsed < 0:
        return elapsed < -CLOCK_SKEW_SECONDS
    return elapsed < MIN_FORM_SECONDS or elapsed > MAX_FORM_SECONDS


@ratelimit(key="ip", rate="4/10m", block=True)
@ratelimit(key="ip", rate="20/h", block=True)
def submit_inquiry(request):
    if request.method != "POST":
        return redirect("catalog:index")

    from utils.client_ip import get_client_ip

    client_ip = get_client_ip(request) or "unknown"

    # Honeypots: bots fill them, humans leave empty.
    if request.POST.get("website") or request.POST.get("company"):
        logger.warning("Honeypot triggered for lead form (ip=%s)", client_ip)
        return _fake_success(request)

    if _is_bot_timing(request):
        logger.warning("Lead form timing trap (ip=%s)", client_ip)
        return _fake_success(request)

    form = InquiryForm(request.POST)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)
        messages.error(
            request,
            "Проверьте имя, город (кириллицей) и российский телефон (+7 / 8).",
        )
        return _safe_redirect(request)

    inquiry = form.save(commit=False)
    cooldown_from = timezone.now() - timedelta(minutes=10)
    cooldown_key = f"lead_cooldown:{inquiry.phone}"
    cooldown_msg = "Повторная заявка с этого номера возможна через 10 минут."

    # Atomic short-TTL lock closes the check-then-insert race under concurrency.
    if not cache.add(cooldown_key, "1", timeout=COOLDOWN_SECONDS):
        return _cooldown_response(request, cooldown_msg)

    if Inquiry.objects.filter(
        phone=inquiry.phone, created_at__gte=cooldown_from
    ).exists():
        return _cooldown_response(request, cooldown_msg)

    inquiry.source = request.META.get("HTTP_REFERER", "")[:255]
    inquiry.referer = request.META.get("HTTP_REFERER", "")[:500]
    inquiry.utm_source = _pick_utm(request, "utm_source", 100)
    inquiry.utm_medium = _pick_utm(request, "utm_medium", 100)
    inquiry.utm_campaign = _pick_utm(request, "utm_campaign", 120)
    inquiry.session_key = request.session.session_key or ""
    inquiry.visitor_id = (
        request.session.get("analytics_visitor_id")
        or request.session.session_key
        or ""
    )[:64]
    try:
        inquiry.save()
    except Exception:
        cache.delete(cooldown_key)
        logger.exception("Inquiry save failed (ip=%s)", client_ip)
        raise
    send_inquiry_notification(inquiry)
    logger.info("New inquiry saved (id=%s)", inquiry.pk)

    if _is_ajax(request):
        return JsonResponse({"status": "success", "message": SUCCESS_MESSAGE})
    messages.success(request, SUCCESS_MESSAGE)
    return _safe_redirect(request)
