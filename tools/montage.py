"""Put several screenshots side by side with captions (for evidence files).

Usage: python tools/montage.py OUT.png "Caption=path.png" ... [--height 900]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
height = 900
if "--height" in args:
    i = args.index("--height")
    height = int(args[i + 1])
    del args[i:i + 2]
out, items = args[0], args[1:]
fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
font = next((ImageFont.truetype(f, 18) for f in fonts if Path(f).exists()), ImageFont.load_default())
tiles = []
for item in items:
    cap, path = item.split("=", 1)
    im = Image.open(path).convert("RGB")
    im = im.crop((0, 0, im.width, min(height, im.height)))
    tiles.append((cap, im))
w = sum(im.width for _, im in tiles) + 20 * (len(tiles) + 1)
h = max(im.height for _, im in tiles) + 60
canvas = Image.new("RGB", (w, h), "white")
d = ImageDraw.Draw(canvas)
x = 20
for cap, im in tiles:
    d.text((x, 15), cap, fill="black", font=font)
    canvas.paste(im, (x, 45))
    d.rectangle([x - 1, 44, x + im.width, 45 + im.height], outline="#999")
    x += im.width + 20
canvas.save(out)
print("wrote", out, canvas.size)
