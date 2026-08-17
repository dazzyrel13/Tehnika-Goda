from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.tests_security import _admin_path


@override_settings(
    ADMIN_LOGIN_EMAIL_APPROVAL=True,
    ADMIN_LOGIN_APPROVAL_VIA="telegram",
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_CHAT_ID="-100123",
    ALLOW_OPEN_ADMIN=True,
)
class AdminTelegramApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(
            "tg-admin",
            "tg@example.com",
            "correct-horse-12",
        )

    @patch("core.tasks.send_admin_login_approval_telegram_task.delay")
    def test_login_queues_telegram_approval(self, mock_delay):
        self.client.force_login(self.user)
        mock_delay.assert_called_once()
        response = self.client.get(_admin_path(), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/pending/", response.url)

    @patch("core.tasks.send_admin_login_approval_telegram_task.delay")
    def test_pending_page_mentions_telegram(self, _mock_delay):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_login_pending"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Telegram")
