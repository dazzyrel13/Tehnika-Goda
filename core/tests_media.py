import tempfile
from pathlib import Path

from django.test import TestCase, override_settings


class ServeMediaTests(TestCase):
    def test_serves_uploaded_image(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            (root / "cars").mkdir()
            photo = root / "cars" / "bora.webp"
            photo.write_bytes(b"RIFF....WEBP")
            with override_settings(MEDIA_ROOT=str(root)):
                response = self.client.get("/media/cars/bora.webp")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["Content-Type"], "image/webp")
                    self.assertIn("inline", response.get("Content-Disposition", ""))
                finally:
                    getattr(response, "close", lambda: None)()

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                response = self.client.get("/media/../core/settings.py")
            self.assertIn(response.status_code, (400, 404))

    def test_pdf_is_attachment(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            with override_settings(MEDIA_ROOT=str(root)):
                response = self.client.get("/media/report.pdf")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("attachment", response.get("Content-Disposition", ""))
                finally:
                    getattr(response, "close", lambda: None)()
