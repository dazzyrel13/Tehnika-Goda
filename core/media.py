"""Serve user uploads in production (host nginx proxies /media/ to Gunicorn)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.views.static import serve

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}


def serve_media(request, path: str):
    """
    Django does not serve MEDIA_ROOT when DEBUG=False.
    Timeweb host nginx currently proxies everything to the app, so photos
    would 404 without this view.

    PDFs stay as attachments to avoid inline XSS via /media/*.pdf.
    Images are served inline so the gallery can show them instead of downloading.
    """
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        response["Content-Type"] = "application/pdf"
        response["Content-Disposition"] = "attachment"
    elif suffix in IMAGE_SUFFIXES:
        response["Content-Type"] = IMAGE_TYPES[suffix]
        response["Content-Disposition"] = "inline"
    return response
