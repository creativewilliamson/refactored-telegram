"""Text-only Open Graph image (1200x630 PNG). No logos, no brand images.

Every line is measured with the real font and shrunk until it fits inside
the margins, so nothing is cut off at the edges (layout() returns the boxes
so the tests can check that).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

W, H = 1200, 630
MARGIN = 80                 # left and right
BAND_TOP = 590              # red band along the bottom
NAVY = (11, 42, 74)
RED = (178, 34, 52)
WHITE = (255, 255, 255)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# (text, largest font size, top y)
LINES = [
    (config.SITE_NAME, 104, 90),
    ("Veterans Day 2026 offers near you", 58, 240),
    ("Enter your ZIP. See free meals and deals", 44, 340),
    ("for veterans and service members.", 44, 400),
    ("Free. No sign-up. Your ZIP stays on your phone.", 36, 490),
]


def _font(size: int):
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def layout() -> list[tuple[str, object, tuple[int, int], tuple[int, int, int, int]]]:
    """(text, font, position, ink box) for each line, each fitted to the width."""
    draw = ImageDraw.Draw(Image.new("RGB", (W, H)))
    out = []
    for text, size, y in LINES:
        font = _font(size)
        while size > 12 and draw.textlength(text, font=font) > W - 2 * MARGIN:
            size -= 2
            font = _font(size)
        out.append((text, font, (MARGIN, y), draw.textbbox((MARGIN, y), text, font=font)))
    return out


def write_image(path: Path) -> None:
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, BAND_TOP, W, H], fill=RED)
    for text, font, xy, _box in layout():
        draw.text(xy, text, font=font, fill=WHITE)
    img.save(path, "PNG", optimize=True)
