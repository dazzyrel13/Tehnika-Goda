import hashlib
import logging
import re

from django.conf import settings

from catalog.models import Vehicle
from core.admin_url import DEFAULT_ADMIN_URL_PREFIX

from .tasks import persist_visit_event, record_visit_event_task

logger = logging.getLogger(__name__)

_BOT_UA = re.compile(
    r"(bot|crawler|spider|slurp|facebookexternalhit|preview|wget|curl|python-requests)",
    re.I,
)


class VisitAnalyticsMiddleware:
    BASE_SKIP_PREFIXES = (
        "/static/",
        "/media/",
        "/ckeditor5/",
        "/leads/",
        "/utils/",
        "/healthz/",
        "/sitemap.xml",
        "/robots.txt",
        "/yandex_",
        "/google",
        "/sw.js",
        "/manifest.json",
    )
    VEHICLE_PATH_RE = re.compile(r"^/catalog/vehicle/(?P<slug>[-a-zA-Z0-9_]+)/?$")
    UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign")

    def __init__(self, get_response):
        self.get_response = get_response
        prefix = (
            getattr(settings, "ADMIN_URL_PREFIX", DEFAULT_ADMIN_URL_PREFIX) or ""
        ).strip("/")
        admin_skip = f"/{prefix}/" if prefix else f"/{DEFAULT_ADMIN_URL_PREFIX.strip('/')}/"
        self.skip_prefixes = self.BASE_SKIP_PREFIXES + (admin_skip,)

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._log_visit(request, response)
        except Exception:
            logger.exception("Visit analytics logging failed")
        return response

    def _log_visit(self, request, response):
        if request.method != "GET":
            return
        if response.status_code >= 400:
            return
        path = request.path or "/"
        if any(path.startswith(prefix) for prefix in self.skip_prefixes):
            return

        accept = request.META.get("HTTP_ACCEPT", "")
        if accept and "text/html" not in accept and "*/*" not in accept:
            return

        user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
        if not user_agent or _BOT_UA.search(user_agent):
            return

        from django.core.cache import cache

        from utils.client_ip import get_client_ip

        ip_address = get_client_ip(request)
        rl_key = f"analytics:rl:{ip_address or '0'}"
        if not cache.add(rl_key, 1, timeout=60):
            try:
                hits = cache.incr(rl_key)
            except ValueError:
                hits = 1
            if hits > 90:
                return

        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key or ""

        visitor_id = self._build_visitor_id(session_key, ip_address, user_agent)
        if request.session.get("analytics_visitor_id") != visitor_id:
            request.session["analytics_visitor_id"] = visitor_id
        referer = (request.META.get("HTTP_REFERER", "") or "")[:500]
        utm = self._capture_utm(request)

        vehicle_id = None
        is_vehicle_page = False
        match = self.VEHICLE_PATH_RE.match(path)
        if match:
            is_vehicle_page = True
            vehicle = (
                Vehicle.objects.filter(slug=match.group("slug")).only("id").first()
            )
            if vehicle:
                vehicle_id = vehicle.id

        store_ip = getattr(settings, "ANALYTICS_STORE_IP", False)
        payload = {
            "visitor_id": visitor_id,
            "session_key": session_key,
            "ip_address": ip_address if store_ip else None,
            "user_agent": user_agent,
            "path": path[:255],
            "referer": referer,
            "utm_source": utm.get("utm_source", ""),
            "utm_medium": utm.get("utm_medium", ""),
            "utm_campaign": utm.get("utm_campaign", ""),
            "vehicle_id": vehicle_id,
            "is_vehicle_page": is_vehicle_page,
        }
        self._enqueue_or_persist(payload)

    @staticmethod
    def _enqueue_or_persist(payload: dict) -> None:
        if getattr(settings, "ANALYTICS_ASYNC", True):
            try:
                record_visit_event_task.delay(payload)
                return
            except Exception:
                logger.warning(
                    "Async visit enqueue failed; falling back to sync write",
                    exc_info=False,
                )
        persist_visit_event(payload)

    @staticmethod
    def _build_visitor_id(session_key, ip_address, user_agent):
        raw = f"{session_key}|{ip_address or ''}|{user_agent}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _capture_utm(self, request):
        utm = {}
        for key in self.UTM_KEYS:
            value = (request.GET.get(key) or "").strip()[:120]
            if value:
                request.session[key] = value
            utm[key] = request.session.get(key, "")
        return utm
