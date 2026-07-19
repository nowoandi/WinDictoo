"""Generate assets/windictoo.ico from the in-app mic glyph."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "windictoo.ico"


def render(size: int, color=(70, 130, 220)) -> Image.Image:
    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24 * s, 10 * s, 40 * s, 40 * s], radius=8 * s, fill=color)
    d.arc([16 * s, 26 * s, 48 * s, 50 * s], start=0, end=180, fill=color, width=max(2, int(5 * s)))
    d.line([32 * s, 48 * s, 32 * s, 56 * s], fill=color, width=max(2, int(5 * s)))
    d.line([22 * s, 56 * s, 42 * s, 56 * s], fill=color, width=max(2, int(5 * s)))
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = render(256)
    base.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
