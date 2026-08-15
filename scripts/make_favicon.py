"""Generate favicon PNGs/ICO from the site emblem (local tooling)."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static" / "images" / "logo_emblem.webp"
OUT_DIR = ROOT / "static" / "images"


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    print("emblem size", im.size, "mode", im.mode)

    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)

    for size, name in [
        (32, "favicon-32.png"),
        (48, "favicon-48.png"),
        (180, "favicon-180.png"),
    ]:
        resized = canvas.resize((size, size), Image.Resampling.LANCZOS)
        path = OUT_DIR / name
        resized.save(path, "PNG")
        print("wrote", path, size)

    ico_path = OUT_DIR / "favicon.ico"
    sizes = [
        canvas.resize((size, size), Image.Resampling.LANCZOS) for size in (16, 32, 48)
    ]
    sizes[0].save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=sizes[1:],
    )
    print("wrote", ico_path)


if __name__ == "__main__":
    main()
