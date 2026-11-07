"""Text-only Open Graph image (1200x630 PNG). No logos, no brand images."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (11, 42, 74)
RED = (178, 34, 52)
WHITE = (255, 255, 255)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int):
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def write_image(path: Path) -> None:
    img = Image.new("RGB", (1200, 630), NAVY)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 590, 1200, 630], fill=RED)
    draw.text((80, 110), "VetsEatFree", font=_font(96), fill=WHITE)
    draw.text((80, 250), "Veterans Day 2026 offers near you", font=_font(58), fill=WHITE)
    draw.text((80, 350), "Enter your ZIP. See free meals and deals", font=_font(44), fill=WHITE)
    draw.text((80, 410), "for veterans and service members.", font=_font(44), fill=WHITE)
    draw.text((80, 500), "Free. No sign-up. Your ZIP stays on your phone.", font=_font(36), fill=WHITE)
    img.save(path, "PNG", optimize=True)
