"""Validate uploaded files are real PDFs (extension + magic bytes)."""

from __future__ import annotations

from django.core.exceptions import ValidationError


PDF_MAGIC = b"%PDF-"


def validate_pdf_upload(file_obj) -> None:
    """Raise ValidationError if upload is not a PDF by name and content."""
    name = getattr(file_obj, "name", "") or ""
    if not name.lower().endswith(".pdf"):
        raise ValidationError("Допускаются только PDF-файлы (.pdf).")

    try:
        pos = file_obj.tell()
    except Exception:
        pos = None

    try:
        header = file_obj.read(5)
    except Exception as exc:
        raise ValidationError("Не удалось прочитать файл.") from exc
    finally:
        if pos is not None:
            try:
                file_obj.seek(pos)
            except Exception:
                pass

    if header != PDF_MAGIC:
        raise ValidationError("Файл не является корректным PDF.")
