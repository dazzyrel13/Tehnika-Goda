"""Обработчик django-ratelimit: 429 вместо необработанного 500."""

from django.http import HttpResponse, JsonResponse


def ratelimited_error(request, exception):
    message = "Слишком много запросов. Попробуйте чуть позже."
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or (
        request.content_type and "application/json" in request.content_type
    ):
        return JsonResponse(
            {"status": "error", "errors": {"__all__": [message]}},
            status=429,
        )
    return HttpResponse(message, status=429, content_type="text/plain; charset=utf-8")
