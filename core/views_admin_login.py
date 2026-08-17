"""Views for email-approved admin login."""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from core.admin_login_approval import (
    approval_enabled,
    approval_via,
    approve_session,
    is_session_approved,
    parse_approval_token,
    queue_approval_notification,
)
from core.admin_url import DEFAULT_ADMIN_URL_PREFIX


def _admin_index_path() -> str:
    from django.conf import settings

    prefix = (settings.ADMIN_URL_PREFIX or DEFAULT_ADMIN_URL_PREFIX).lstrip("/")
    if not prefix.endswith("/"):
        prefix += "/"
    return "/" + prefix


class AdminLoginPendingView(View):
    def get(self, request):
        if not approval_enabled():
            return redirect(_admin_index_path())
        user = request.user
        if not user.is_authenticated or not (user.is_staff or user.is_superuser):
            return redirect_to_login(request.get_full_path())
        if is_session_approved(request.session.session_key):
            return redirect(_admin_index_path())
        return render(
            request,
            "admin_login_pending.html",
            {
                "notice_sent": request.session.get("admin_login_notice_sent", True),
                "approval_via": approval_via(),
                "approval_email": getattr(
                    settings, "ADMIN_LOGIN_APPROVAL_EMAIL", ""
                ),
                "status_url": reverse("admin_login_status"),
                "resend_url": reverse("admin_login_resend"),
            },
        )


class AdminLoginStatusView(View):
    def get(self, request):
        if not approval_enabled():
            return JsonResponse({"approved": True})
        approved = is_session_approved(request.session.session_key)
        return JsonResponse({"approved": approved})


class AdminLoginApproveView(View):
    def get(self, request, token):
        parsed = parse_approval_token(token)
        if not parsed:
            return render(
                request,
                "admin_login_approve_result.html",
                {"ok": False, "message": "Ссылка недействительна или устарела."},
                status=400,
            )
        session_key, _user_id = parsed
        if not approve_session(session_key):
            return render(
                request,
                "admin_login_approve_result.html",
                {"ok": False, "message": "Сессия уже не ожидает подтверждения."},
                status=400,
            )
        return render(
            request,
            "admin_login_approve_result.html",
            {
                "ok": True,
                "message": "Вход подтверждён. Вернитесь в браузер, где открыта админка.",
            },
        )


class AdminLoginResendView(View):
    def post(self, request):
        if not approval_enabled():
            return JsonResponse({"ok": False, "error": "disabled"}, status=400)
        user = request.user
        if not user.is_authenticated or not (user.is_staff or user.is_superuser):
            return JsonResponse({"ok": False, "error": "auth"}, status=403)
        if is_session_approved(request.session.session_key):
            return JsonResponse({"ok": True, "approved": True})
        sent = queue_approval_notification(
            session_key=request.session.session_key,
            user=user,
            request=request,
        )
        request.session["admin_login_notice_sent"] = sent
        return JsonResponse({"ok": sent})
