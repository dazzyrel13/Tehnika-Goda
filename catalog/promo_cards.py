"""Generate branded social-media promo cards without changing catalog data."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1920
INK = (10, 22, 40)
PANEL = (20, 35, 55)
GOLD = (255, 179, 0)
WHITE = (248, 249, 250)
MUTED = (171, 184, 199)


def _font(size, bold=False):
    """Use a Cyrillic-capable font in both the Linux container and Windows."""
    import os

    candidates = (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if os.name != "nt"
        else ("C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf")
    )
    for path in (candidates[0] if bold else candidates[1], candidates[1]):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit(field, size):
    field.open("rb")
    try:
        return ImageOps.fit(Image.open(field).convert("RGB"), size, Image.Resampling.LANCZOS)
    finally:
        field.close()


def _text(draw, xy, value, font, fill=WHITE, anchor=None):
    draw.text(xy, str(value), font=font, fill=fill, anchor=anchor)


def _wrap(draw, value, font, max_width, limit=2):
    words = str(value).split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:limit] or ["Автомобиль"]


def _gallery(vehicle):
    from .templatetags.catalog_extras import vehicle_gallery_images

    return vehicle_gallery_images(vehicle)[:4]


def render_vehicle_card(vehicle):
    """Return a branded 1080x1920 WebP-ready promo card."""
    canvas = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, 16), fill=GOLD)
    images = _gallery(vehicle)
    if images:
        canvas.paste(_fit(images[0], (WIDTH - 72, 930)), (36, 58))
        if len(images) > 1:
            thumb_y, thumb_w, gap = 1010, 234, 18
            for index, image in enumerate(images[1:4]):
                canvas.paste(_fit(image, (thumb_w, 170)), (36 + index * (thumb_w + gap), thumb_y))
    else:
        draw.rounded_rectangle((36, 58, WIDTH - 36, 988), 28, fill=PANEL)
        _text(draw, (WIDTH // 2, 520), "ФОТО НЕТ", _font(52, True), MUTED, "mm")
    _text(draw, (58, 42), "ТЕХНИКА ГОДА", _font(27, True), WHITE)
    draw.ellipse((WIDTH - 112, 38, WIDTH - 58, 92), fill=GOLD)
    _text(draw, (WIDTH - 85, 65), "TG", _font(20, True), INK, "mm")
    title_font = _font(54, True)
    title = vehicle.title or f"{vehicle.brand.name} {vehicle.model}".strip()
    for index, line in enumerate(_wrap(draw, title, title_font, WIDTH - 116)):
        _text(draw, (58, 1245 + index * 66), line, title_font, WHITE)
    _text(draw, (58, 1390), "АВТО ИЗ КИТАЯ ПОД ЗАКАЗ", _font(23, True), GOLD)
    draw.rounded_rectangle((36, 1470, WIDTH - 36, 1712), 28, fill=PANEL, outline=(53, 70, 92), width=2)
    specs = [("ГОД", vehicle.year or "—"), ("ПРОБЕГ", f"{vehicle.mileage:,} км".replace(",", " ") if vehicle.mileage else "—"), ("ДВИГАТЕЛЬ", vehicle.get_engine_type_display() if vehicle.engine_type else "—"), ("КУЗОВ", vehicle.body_type or "—")]
    for index, (label, value) in enumerate(specs):
        x, y = 72 + (index % 2) * 480, 1510 + (index // 2) * 105
        _text(draw, (x, y), label, _font(18, True), MUTED)
        _text(draw, (x, y + 34), value, _font(28, True), WHITE)
    price = f"{vehicle.price_rub:,.0f} ₽".replace(",", " ") if vehicle.price_rub else "ЦЕНА ПО ЗАПРОСУ"
    _text(draw, (58, 1770), price, _font(47, True), GOLD)
    _text(draw, (WIDTH - 58, 1778), "tehnikagoda.ru", _font(27, True), WHITE, "ra")
    _text(draw, (58, 1854), "Проверка до оплаты  •  Гарантия на ДВС и КПП", _font(19), MUTED)
    return canvas


def build_promo_archive(vehicles):
    """Return (filename, bytes) as WebP or ZIP of WebP cards."""
    vehicles = list(vehicles)
    if len(vehicles) == 1:
        output = BytesIO()
        render_vehicle_card(vehicles[0]).save(output, "WEBP", quality=92, method=6)
        return f"promo-{vehicles[0].slug or vehicles[0].pk}.webp", output.getvalue()
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        for vehicle in vehicles:
            output = BytesIO()
            render_vehicle_card(vehicle).save(output, "WEBP", quality=92, method=6)
            zipped.writestr(f"promo-{vehicle.slug or vehicle.pk}.webp", output.getvalue())
    return "promo-cards.zip", archive.getvalue()