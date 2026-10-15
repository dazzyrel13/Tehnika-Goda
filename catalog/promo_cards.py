"""Generate social-media promo cards without changing catalog data."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH, HEIGHT = 1080, 1920
NAVY = (10, 22, 40)
BLUE = (35, 75, 125)
YELLOW = (255, 179, 0)
WHITE = (245, 247, 250)
MUTED = (174, 187, 204)


def _font(size, bold=False):
    names = (
        ("C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf")
        if __import__("os").name == "nt"
        else ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for name in (names[0] if bold else names[1], names[1]):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _fit_image(field, size):
    field.open("rb")
    try:
        image = Image.open(field).convert("RGB")
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    finally:
        field.close()


def _text(draw, xy, value, font, fill=WHITE, anchor=None):
    draw.text(xy, str(value), font=font, fill=fill, anchor=anchor)


def render_vehicle_card(vehicle):
    """Return a 1080x1920 WebP promo card for a Vehicle instance."""
    canvas = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, 18), fill=YELLOW)

    if vehicle.main_image:
        hero = _fit_image(vehicle.main_image, (WIDTH, 900))
        canvas.paste(hero, (0, 18))
        overlay = Image.new("RGBA", hero.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle((0, 500, WIDTH, 900), fill=(10, 22, 40, 190))
        canvas.paste(overlay, (0, 18), overlay)
    else:
        draw.rounded_rectangle((55, 80, WIDTH - 55, 780), 28, fill=(24, 45, 70))
        _text(draw, (WIDTH // 2, 430), "ФОТО НЕТ", _font(52, True), MUTED, "mm")

    _text(draw, (62, 72), "ТЕХНИКА ГОДА", _font(28, True), WHITE)
    title = vehicle.title or f"{vehicle.brand.name} {vehicle.model}".strip()
    _text(draw, (62, 790), title[:42], _font(58, True), WHITE)
    _text(draw, (62, 870), "АВТО ИЗ КИТАЯ ПОД ЗАКАЗ", _font(25, True), YELLOW)

    draw.rounded_rectangle((55, 980, WIDTH - 55, 1350), 30, fill=(19, 39, 65), outline=(48, 78, 112), width=2)
    specs = [
        ("Год", vehicle.year or "—"),
        ("Пробег", f"{vehicle.mileage:,} км".replace(",", " ") if vehicle.mileage else "—"),
        ("Двигатель", vehicle.get_engine_type_display() if vehicle.engine_type else "—"),
        ("Кузов", vehicle.body_type or "—"),
    ]
    for index, (label, value) in enumerate(specs):
        x = 95 + (index % 2) * 480
        y = 1035 + (index // 2) * 145
        _text(draw, (x, y), label.upper(), _font(22, True), MUTED)
        _text(draw, (x, y + 42), value, _font(31, True), WHITE)

    price = f"{vehicle.price_rub:,.0f} ₽".replace(",", " ") if vehicle.price_rub else "ЦЕНА ПО ЗАПРОСУ"
    _text(draw, (62, 1450), price, _font(58, True), YELLOW)
    _text(draw, (62, 1535), "Проверка до оплаты • Гарантия на ДВС и КПП", _font(23), MUTED)
    draw.rounded_rectangle((55, 1665, WIDTH - 55, 1815), 26, fill=BLUE)
    _text(draw, (WIDTH // 2, 1715), "tehnikagoda.ru", _font(40, True), WHITE, "mm")
    _text(draw, (WIDTH // 2, 1770), "Напишите нам — подберём автомобиль", _font(22), WHITE, "mm")
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