"""Friendly HTTP error pages for production (plain Django defaults are opaque)."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent, TooManyFilesSent
from django.http import HttpResponseBadRequest
from django.template.loader import render_to_string
from django.views.defaults import bad_request as django_bad_request


def bad_request(request, exception):
    """Explain upload limit / parse failures instead of bare «Bad Request (400)»."""
    if isinstance(exception, TooManyFilesSent):
        limit = getattr(settings, "DATA_UPLOAD_MAX_NUMBER_FILES", 100)
        message = (
            f"Слишком много файлов за один раз (лимит {limit}). "
            "Уменьшите пачку фото и отправьте снова — остальное можно догрузить в карточке."
        )
        return _render_upload_error(message)
    if isinstance(exception, RequestDataTooBig):
        message = (
            "Размер запроса слишком большой (тяжёлые фото). "
            "Загрузите меньше снимков или сожмите JPEG и попробуйте снова."
        )
        return _render_upload_error(message)
    if isinstance(exception, TooManyFieldsSent):
        message = (
            "В форме слишком много полей. Обновите страницу и попробуйте снова "
            "с меньшей пачкой фото."
        )
        return _render_upload_error(message)

    return django_bad_request(request, exception)


def _render_upload_error(message: str) -> HttpResponseBadRequest:
    # No request context — SEO/context processors must not hit the DB on a broken POST.
    try:
        html = render_to_string("400_upload.html", {"message": message})
    except Exception:
        html = (
            "<!DOCTYPE html><html lang='ru'><body>"
            f"<h1>Не удалось принять запрос</h1><p>{message}</p>"
            "</body></html>"
        )
    return HttpResponseBadRequest(html)
