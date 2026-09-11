"""Tests for /healthz/ readiness probe."""

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch


class HealthzTests(TestCase):
    def test_ok_when_db_and_redis_up_loopback_is_detailed(self):
        response = self.client.get(reverse("healthz"), REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["db"])
        self.assertTrue(data["redis"])

    def test_public_response_hides_dependency_flags(self):
        response = self.client.get(reverse("healthz"), REMOTE_ADDR="203.0.113.10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertNotIn("db", data)
        self.assertNotIn("redis", data)

    @override_settings(HEALTHZ_TOKEN="probe-secret")
    def test_token_unlocks_detailed_payload(self):
        response = self.client.get(
            reverse("healthz"),
            REMOTE_ADDR="203.0.113.10",
            HTTP_X_HEALTHZ_TOKEN="probe-secret",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["db"])
        self.assertTrue(data["redis"])

    def test_unhealthy_when_db_down(self):
        with patch("core.health._check_db", return_value=False):
            response = self.client.get(reverse("healthz"), REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unhealthy")
        self.assertFalse(response.json()["db"])

    def test_unhealthy_when_redis_down(self):
        with patch("core.health._check_redis", return_value=False):
            response = self.client.get(reverse("healthz"), REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["redis"])

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/"])
    def test_healthz_not_redirected_when_ssl_redirect_on(self):
        response = self.client.get(
            reverse("healthz"), REMOTE_ADDR="127.0.0.1", secure=False
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class HealthzSkipAnalyticsTests(SimpleTestCase):
    def test_healthz_is_in_analytics_skip_prefixes(self):
        from analytics.middleware import VisitAnalyticsMiddleware

        self.assertIn("/healthz/", VisitAnalyticsMiddleware.BASE_SKIP_PREFIXES)
