import re

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.admin_url import DEFAULT_ADMIN_URL_PREFIX


def _admin_path() -> str:
    prefix = (settings.ADMIN_URL_PREFIX or DEFAULT_ADMIN_URL_PREFIX).lstrip("/")
    if not prefix.endswith("/"):
        prefix += "/"
    return "/" + prefix


@override_settings(ADMIN_ALLOWED_IPS=["203.0.113.50"], TRUST_PROXY_HEADERS=True)
class AdminIPAllowlistTests(TestCase):
    def test_blocks_other_ip(self):
        response = self.client.get(
            _admin_path(),
            HTTP_X_REAL_IP="198.51.100.1",
        )
        self.assertEqual(response.status_code, 403)

    def test_allows_listed_ip(self):
        response = self.client.get(
            _admin_path(),
            HTTP_X_REAL_IP="203.0.113.50",
        )
        # May redirect to login (302) or 200 — must not be 403
        self.assertNotEqual(response.status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS=["not-an-ip"])
    def test_invalid_allowlist_entries_deny_all(self):
        response = self.client.get(_admin_path())
        self.assertEqual(response.status_code, 403)


@override_settings(
    ADMIN_URL_PREFIX="custom-admin-gate/",
    ADMIN_ALLOWED_IPS=["203.0.113.50"],
    TRUST_PROXY_HEADERS=True,
)
class AdminUrlPrefixConsistencyTests(TestCase):
    def test_allowlist_follows_admin_url_prefix_setting(self):
        from core.security_middleware import _admin_prefix

        self.assertEqual(_admin_prefix(), "/custom-admin-gate/")
        blocked = self.client.get(
            "/custom-admin-gate/",
            HTTP_X_REAL_IP="198.51.100.1",
        )
        self.assertEqual(blocked.status_code, 403)
        allowed = self.client.get(
            "/custom-admin-gate/",
            HTTP_X_REAL_IP="203.0.113.50",
        )
        # URLconf is loaded at import time; 404 is fine — must not be 403
        self.assertNotEqual(allowed.status_code, 403)


@override_settings(RATELIMIT_ENABLE=False)
class SecurityHeadersTests(TestCase):
    def test_csp_present_on_json_endpoint(self):
        response = self.client.get(reverse("catalog:search_ajax"), {"q": "xx"})
        self.assertIn("Content-Security-Policy", response)
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src", csp)
        self.assertRegex(csp, r"script-src 'self'")
        self.assertNotRegex(csp, r"script-src[^;]*unsafe-inline")
        self.assertRegex(csp, r"img-src 'self' data: blob:")
        self.assertNotRegex(csp, r"img-src[^;]*https:")
        self.assertNotIn("fonts.googleapis.com", csp)
        self.assertNotIn("fonts.gstatic.com", csp)
        self.assertRegex(csp, r"font-src 'self'")
        self.assertEqual(
            response.get("Referrer-Policy"), "strict-origin-when-cross-origin"
        )
        self.assertEqual(response.get("Cross-Origin-Opener-Policy"), "same-origin")
        self.assertEqual(response.get("Cross-Origin-Resource-Policy"), "same-origin")

    @override_settings(YANDEX_METRIKA_ID="12345678")
    def test_csp_allows_yandex_metrika_when_configured(self):
        response = self.client.get(reverse("catalog:search_ajax"), {"q": "xx"})
        csp = response["Content-Security-Policy"]
        self.assertIn("mc.yandex.ru", csp)
        self.assertRegex(csp, r"script-src[^;]*https://mc\.yandex\.ru")

    def test_home_exposes_metrika_data_attr_when_configured(self):
        with override_settings(YANDEX_METRIKA_ID="87654321"):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-yandex-metrika-id="87654321"')

    def test_public_html_has_no_inline_javascript(self):
        urls = [
            reverse("home"),
            reverse("leasing"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                for match in re.finditer(
                    r"<script\b([^>]*)>", html, flags=re.IGNORECASE
                ):
                    attrs = match.group(1)
                    if re.search(r"\bsrc\s*=", attrs, flags=re.IGNORECASE):
                        continue
                    self.assertRegex(
                        attrs,
                        r"""type\s*=\s*['"]application/ld\+json['"]""",
                        msg=f"Inline executable script is not allowed on {url}: <script{attrs}>",
                    )

    def test_admin_csp_allows_inline_scripts(self):
        response = self.client.get(_admin_path())
        csp = response.get("Content-Security-Policy", "")
        self.assertRegex(csp, r"script-src[^;]*unsafe-inline")
        self.assertRegex(csp, r"img-src[^;]*https:")

    def test_robots_does_not_disclose_custom_admin_path(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /healthz/", body)
        self.assertNotIn("h_portal-elite-x3", body)
        self.assertNotIn(DEFAULT_ADMIN_URL_PREFIX.rstrip("/"), body)
        self.assertNotIn(settings.ADMIN_URL_PREFIX.rstrip("/"), body)
        self.assertNotIn("/catalog/dealer/", body)


class AdminTwoFactorTests(TestCase):
    def test_login_is_under_hidden_admin_prefix(self):
        login_url = reverse("two_factor:login")
        self.assertTrue(login_url.startswith(_admin_path()))
        self.assertIn("/account/login/", login_url)

    def test_staff_without_otp_cannot_open_admin(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_superuser(
            "otp-admin",
            "otp@example.com",
            "correct-horse-12",
        )
        self.client.force_login(user)
        response = self.client.get(_admin_path(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], reverse("two_factor:login"))

    def test_stock_admin_login_redirects_to_two_factor(self):
        response = self.client.get(_admin_path() + "login/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response.url)

    def test_login_page_ok(self):
        response = self.client.get(reverse("two_factor:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Техника Года")


@override_settings(ADMIN_ALLOWED_IPS=["203.0.113.50"], TRUST_PROXY_HEADERS=True)
class TwoFactorLoginAllowlistTests(TestCase):
    def test_login_blocked_for_other_ip(self):
        response = self.client.get(
            reverse("two_factor:login"),
            HTTP_X_REAL_IP="198.51.100.1",
        )
        self.assertEqual(response.status_code, 403)

    def test_login_allowed_for_listed_ip(self):
        response = self.client.get(
            reverse("two_factor:login"),
            HTTP_X_REAL_IP="203.0.113.50",
        )
        self.assertNotEqual(response.status_code, 403)


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class AdminLoginLockoutTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username="lock-staff",
            password="correct-horse-12",
            is_staff=True,
        )

    def _attempt(self):
        return self.client.post(
            reverse("two_factor:login"),
            {
                "auth-username": "lock-staff",
                "auth-password": "wrong-password",
                "login_view-current_step": "auth",
            },
        )

    def test_lockout_after_repeated_failures(self):
        for _ in range(2):
            response = self._attempt()
            self.assertLess(response.status_code, 400)
        locked = self._attempt()
        self.assertEqual(locked.status_code, 429)
