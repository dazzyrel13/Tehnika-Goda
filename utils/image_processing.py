import os
import re
import uuid
from io import BytesIO

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps

MASTER_MAX_WIDTH = 1600
MASTER_QUALITY = 85
VARIANT_WIDTHS = (400, 800)
VARIANT_QUALITY = 85  # same as master — smaller pixels, not heavier compression
SRCSET_CACHE_TTL = 60 * 60 * 24 * 7
_VARIANT_NAME_RE = re.compile(r"\.w(400|800)\.webp$", re.IGNORECASE)


def _normalize_mode(img: Image.Image) -> Image.Image:
    if img.mode == "P":
        return img.convert("RGBA")
    if img.mode not in ("RGB", "RGBA"):
        return img.convert("RGB")
    return img


def _load_image(image_field) -> Image.Image | None:
    if not image_field:
        return None
    try:
        image_field.open()
    except Exception:
        pass
    try:
        image_field.seek(0)
    except Exception:
        pass
    img = Image.open(image_field)
    img = ImageOps.exif_transpose(img)
    img.load()
    try:
        image_field.seek(0)
    except Exception:
        pass
    return img


def is_new_upload(image_field) -> bool:
    if not image_field:
        return False
    try:
        fh = image_field.file
    except Exception:
        return False
    return isinstance(fh, UploadedFile)


def should_process_image(image_field) -> bool:
    """True for new uploads or non-WebP files. Skip re-decode of saved WebP."""
    if not image_field or not getattr(image_field, "name", None):
        return False
    if is_new_upload(image_field):
        return True
    return not str(image_field.name).lower().endswith(".webp")


def process_image_to_webp(image_field, quality=MASTER_QUALITY, max_width=MASTER_MAX_WIDTH):
    """
    Convert to WebP and downscale if wider than max_width.

    Already-small WebP files are left untouched (no recompress).
    Oversized WebP is resized — that is the only case a .webp is rewritten.
    """
    if not image_field:
        return None

    name = os.path.basename(getattr(image_field, "name", "") or "image")
    is_webp = name.lower().endswith(".webp")
    img = _load_image(image_field)
    if img is None:
        return None

    needs_resize = img.width > max_width
    if is_webp and not needs_resize:
        return None

    img = _normalize_mode(img)
    if needs_resize:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * float(ratio))
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    output = BytesIO()
    img.save(output, format="WEBP", quality=quality, method=6)
    output.seek(0)
    # Short random stem — long original filenames blow ImageField max_length
    # when combined with catalog/vehicles/<slug>/… upload paths.
    return ContentFile(output.read(), name=f"{uuid.uuid4().hex[:12]}.webp")


def is_variant_name(name: str) -> bool:
    return bool(name and _VARIANT_NAME_RE.search(name))


def variant_storage_name(master_name: str, width: int) -> str:
    if master_name.lower().endswith(".webp"):
        return master_name[:-5] + f".w{width}.webp"
    root, _ext = os.path.splitext(master_name)
    return f"{root}.w{width}.webp"


def _srcset_cache_key(master_name: str) -> str:
    return f"img:srcset:{master_name}"


def _store_srcset_cache(master_name: str, candidates: dict[int, str], master_url: str) -> dict:
    payload = {
        "src": "",
        "srcset": "",
        "full_src": master_url,
        "candidates": {str(k): v for k, v in candidates.items()},
    }
    src = candidates.get(800) or master_url
    payload["src"] = src
    payload["srcset"] = ", ".join(
        f"{url} {width}w" for width, url in sorted(candidates.items())
    )
    cache.set(_srcset_cache_key(master_name), payload, SRCSET_CACHE_TTL)
    return payload


def delete_responsive_variants(master_name: str, storage=None) -> None:
    if not master_name or is_variant_name(master_name):
        return
    storage = storage or default_storage
    for width in VARIANT_WIDTHS:
        dest = variant_storage_name(master_name, width)
        try:
            if storage.exists(dest):
                storage.delete(dest)
        except Exception:
            pass
    cache.delete(_srcset_cache_key(master_name))


def write_responsive_variants(image_field) -> None:
    """Write .w400.webp / .w800.webp next to the master. Skip if master is already small."""
    if not image_field or not getattr(image_field, "name", None):
        return
    if is_variant_name(image_field.name):
        return

    storage = getattr(image_field, "storage", None) or default_storage
    try:
        with storage.open(image_field.name, "rb") as fh:
            img = Image.open(fh)
            img = ImageOps.exif_transpose(img)
            img.load()
    except Exception:
        return

    img = _normalize_mode(img)
    master_w = img.width
    try:
        master_url = image_field.url
    except ValueError:
        master_url = storage.url(image_field.name)

    candidates: dict[int, str] = {master_w: master_url}

    for width in VARIANT_WIDTHS:
        dest = variant_storage_name(image_field.name, width)
        if master_w <= width:
            if storage.exists(dest):
                storage.delete(dest)
            continue
        ratio = width / float(master_w)
        resized = img.resize(
            (width, max(1, int(img.height * ratio))),
            Image.Resampling.LANCZOS,
        )
        buf = BytesIO()
        resized.save(buf, format="WEBP", quality=VARIANT_QUALITY, method=6)
        buf.seek(0)
        content = ContentFile(buf.read())
        if storage.exists(dest):
            storage.delete(dest)
        storage.save(dest, content)
        candidates[width] = storage.url(dest)

    _store_srcset_cache(image_field.name, candidates, master_url)


def responsive_attrs(image_field, default_width: int = 800) -> dict:
    """
    src / srcset / full_src for templates.

    Variant URLs are cached after save/backfill so list pages do not stat storage
    on every request. Cache miss still probes existence (old photos).
    """
    empty = {"src": "", "srcset": "", "full_src": ""}
    if not image_field or not getattr(image_field, "name", None):
        return empty

    cached = cache.get(_srcset_cache_key(image_field.name))
    if cached:
        candidates = {
            int(width): url for width, url in (cached.get("candidates") or {}).items()
        }
        master_url = cached.get("full_src") or image_field.url
        src = candidates.get(int(default_width)) or cached.get("src") or master_url
        srcset = cached.get("srcset") or ", ".join(
            f"{url} {width}w" for width, url in sorted(candidates.items())
        )
        return {"src": src, "srcset": srcset, "full_src": master_url}

    storage = getattr(image_field, "storage", None) or default_storage
    try:
        master_url = image_field.url
    except ValueError:
        return empty

    candidates: dict[int, str] = {}
    for width in VARIANT_WIDTHS:
        dest = variant_storage_name(image_field.name, width)
        if storage.exists(dest):
            candidates[width] = storage.url(dest)
    master_w = None
    try:
        with storage.open(image_field.name, "rb") as fh:
            with Image.open(fh) as img:
                master_w = img.width
    except Exception:
        master_w = None
    if master_w:
        candidates[master_w] = master_url
    payload = _store_srcset_cache(image_field.name, candidates, master_url)
    src = candidates.get(int(default_width)) or master_url
    return {"src": src, "srcset": payload["srcset"], "full_src": master_url}


def variant_url(image_field, width: int = 400) -> str:
    attrs = responsive_attrs(image_field, default_width=width)
    return attrs["src"]
