from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.admin_login_approval import is_session_approved, make_approval_token
from core.tests_security import _admin_path


@override_settings(
    ADMIN_LOGIN_EMAIL_APPROVAL=True,
    ADMIN_LOGIN_APPROVAL_EMAIL="owner@example.com",
    ADMIN_ALLOWED_IPS=[],
    ALLOW_OPEN_ADMIN=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.example.com",
    EMAIL_HOST_USER="mail@example.com",
    EMAIL_HOST_PASSWORD="secret",
    DEFAULT_FROM_EMAIL="mail@example.com",
)
class AdminEmailApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(
            "email-admin",
            "staff@example.com",
            "correct-horse-12",
        )

    def test_login_sends_approval_email_and_blocks_admin(self):
        self.client.force_login(self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("owner@example.com", mail.outbox[0].to)
        self.assertIn("подтвердите вход", mail.outbox[0].subject.lower())

        response = self.client.get(_admin_path(), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/pending/", response.url)

    def test_approve_link_grants_session(self):
        self.client.force_login(self.user)
        session_key = self.client.session.session_key
        self.assertFalse(is_session_approved(session_key))

        token = make_approval_token(session_key, self.user.pk)
        approve_url = _admin_path().rstrip("/") + f"/account/login/approve/{token}/"
        response = self.client.get(approve_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_session_approved(session_key))

        pending = self.client.get(reverse("admin_login_status"))
        self.assertEqual(pending.json()["approved"], True)

    def test_pending_page_accessible_without_ip_allowlist(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin_login_pending"),
            HTTP_X_REAL_IP="198.51.100.1",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "owner@example.com")
