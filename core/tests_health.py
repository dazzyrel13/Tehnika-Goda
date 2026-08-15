"""Tests for /healthz/ readiness probe."""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import patch


class HealthzTests(TestCase):
    def test_ok_when_db_and_redis_up(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["db"])
        self.assertTrue(data["redis"])

    def test_unhealthy_when_db_down(self):
        with patch("core.health._check_db", return_value=False):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unhealthy")
        self.assertFalse(response.json()["db"])

    def test_unhealthy_when_redis_down(self):
        with patch("core.health._check_redis", return_value=False):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["redis"])


class HealthzSkipAnalyticsTests(SimpleTestCase):
    def test_healthz_is_in_analytics_skip_prefixes(self):
        from analytics.middleware import VisitAnalyticsMiddleware

        self.assertIn("/healthz/", VisitAnalyticsMiddleware.BASE_SKIP_PREFIXES)
