from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, Category, Vehicle

from .models import VisitEvent
from .tasks import cleanup_old_visit_events_task, persist_visit_event
from .visitor import VISITOR_COOKIE_NAME


@override_settings(ANALYTICS_ASYNC=False, RATELIMIT_ENABLE=False, ANALYTICS_STORE_IP=False)
class VisitAnalyticsMiddlewareTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые"}
        )
        self.brand = Brand.objects.create(name="TestBrand", slug="testbrand")
        self.vehicle = Vehicle.objects.create(
            title="Test Car",
            slug="test-car",
            category=self.category,
            brand=self.brand,
            year=2024,
            price_rub=1000000,
            is_published=True,
        )

    def test_html_get_creates_visit_event_with_cookie_not_session(self):
        response = self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisitEvent.objects.count(), 1)
        event = VisitEvent.objects.get()
        self.assertEqual(event.path, "/")
        self.assertIsNone(event.ip_address)
        self.assertIn(VISITOR_COOKIE_NAME, response.cookies)
        cookie_vid = response.cookies[VISITOR_COOKIE_NAME].value
        self.assertEqual(len(cookie_vid), 32)
        self.assertEqual(event.visitor_id, cookie_vid)
        # CSRF_USE_SESSIONS may create a session for the form token, but analytics
        # must not store visitor id there.
        if Session.objects.exists():
            session_data = Session.objects.get().get_decoded()
            self.assertNotIn("analytics_visitor_id", session_data)
            self.assertNotIn("utm_source", session_data)

    def test_reuses_visitor_cookie(self):
        first = self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        vid = first.cookies[VISITOR_COOKIE_NAME].value
        VisitEvent.objects.all().delete()

        self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        event = VisitEvent.objects.get()
        self.assertEqual(event.visitor_id, vid)

    def test_bots_are_skipped(self):
        response = self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Googlebot/2.1",
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisitEvent.objects.count(), 0)

    def test_static_paths_skipped(self):
        response = self.client.get(
            "/robots.txt",
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/plain",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisitEvent.objects.count(), 0)

    def test_vehicle_page_links_vehicle(self):
        response = self.client.get(
            reverse("catalog:vehicle_detail", kwargs={"slug": self.vehicle.slug}),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(response.status_code, 200)
        event = VisitEvent.objects.get()
        self.assertTrue(event.is_vehicle_page)
        self.assertEqual(event.vehicle_id, self.vehicle.id)

    def test_utm_captured_into_event_and_cookie(self):
        response = self.client.get(
            reverse("home") + "?utm_source=yandex&utm_medium=cpc",
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        event = VisitEvent.objects.get()
        self.assertEqual(event.utm_source, "yandex")
        self.assertEqual(event.utm_medium, "cpc")
        self.assertEqual(response.cookies["utm_source"].value, "yandex")
        if Session.objects.exists():
            session_data = Session.objects.get().get_decoded()
            self.assertNotIn("utm_source", session_data)

    @patch("analytics.middleware.record_visit_event_task.delay")
    @override_settings(ANALYTICS_ASYNC=True)
    def test_async_enqueue_called(self, mock_delay):
        self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        mock_delay.assert_called_once()
        self.assertEqual(VisitEvent.objects.count(), 0)

    @patch(
        "analytics.middleware.record_visit_event_task.delay",
        side_effect=RuntimeError("broker down"),
    )
    @override_settings(ANALYTICS_ASYNC=True)
    def test_async_fallback_to_sync(self, mock_delay):
        self.client.get(
            reverse("home"),
            HTTP_USER_AGENT="Mozilla/5.0 TestBrowser",
            HTTP_ACCEPT="text/html",
        )
        mock_delay.assert_called_once()
        self.assertEqual(VisitEvent.objects.count(), 1)


class AnalyticsTasksTests(TestCase):
    def test_persist_visit_event(self):
        persist_visit_event(
            {
                "visitor_id": "abc123",
                "session_key": "sess",
                "path": "/catalog/",
                "is_vehicle_page": False,
            }
        )
        self.assertEqual(VisitEvent.objects.count(), 1)

    def test_persist_resolves_vehicle_slug(self):
        category, _ = Category.objects.get_or_create(
            slug="cars", defaults={"name": "Легковые"}
        )
        brand = Brand.objects.create(name="SlugBrand", slug="slugbrand")
        vehicle = Vehicle.objects.create(
            title="Slug Car",
            slug="slug-car",
            category=category,
            brand=brand,
            year=2024,
            price_rub=1000000,
            is_published=True,
        )
        persist_visit_event(
            {
                "visitor_id": "abc123",
                "path": f"/catalog/vehicle/{vehicle.slug}/",
                "vehicle_slug": vehicle.slug,
                "is_vehicle_page": True,
            }
        )
        event = VisitEvent.objects.get()
        self.assertEqual(event.vehicle_id, vehicle.id)

    def test_cleanup_old_visit_events(self):
        old = VisitEvent.objects.create(
            visitor_id="old",
            path="/old/",
        )
        VisitEvent.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=120)
        )
        VisitEvent.objects.create(visitor_id="new", path="/new/")

        with self.settings(ANALYTICS_RETENTION_DAYS=90):
            deleted = cleanup_old_visit_events_task()

        self.assertEqual(deleted, 1)
        self.assertEqual(VisitEvent.objects.count(), 1)
        self.assertEqual(VisitEvent.objects.get().visitor_id, "new")

    def test_record_task_ignores_result(self):
        from .tasks import record_visit_event_task

        self.assertTrue(record_visit_event_task.ignore_result)
