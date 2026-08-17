"""Serve user uploads in production (host nginx proxies /media/ to Gunicorn)."""

from __future__ import annotations

from django.conf import settings
from django.views.static import serve


def serve_media(request, path: str):
    """
    Django does not serve MEDIA_ROOT when DEBUG=False.
    Timeweb host nginx currently proxies everything to the app, so photos
    would 404 without this view.

    PDFs stay as attachments to avoid inline XSS via /media/*.pdf.
    """
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    if path.lower().endswith(".pdf"):
        response["Content-Type"] = "application/pdf"
        response["Content-Disposition"] = "attachment"
    return response
