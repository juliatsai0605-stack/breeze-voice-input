"""產生 App 圖示（深色底＋漸層聲波條）：assets/icon.png（1024）與 assets/icon.ico（16～256 多尺寸）。
python scripts/make_icon.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).resolve().parent.parent / "assets"


def lin_grad(c1, c2, angle=45):
    """依角度的線性漸層"""
    g = Image.new("RGB", (S, S))
    px = g.load()
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    for y in range(S):
        for x in range(S):
            t = ((x - S / 2) * dx + (y - S / 2) * dy) / (S * 0.75) + 0.5
            t = min(1, max(0, t))
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return g.convert("RGBA")


def draw_icon():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 陰影
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((70, 92, S - 70, S - 40), radius=230, fill=(0, 0, 0, 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26)))
    # 深藍紫圓角底
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((64, 64, S - 64, S - 64), radius=230, fill=255)
    img.paste(lin_grad((15, 23, 42), (49, 46, 129), 60), (0, 0), m)
    # 五條聲波條（青綠 → 天藍漸層）
    bars = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(bars)
    hs = [0.30, 0.58, 0.88, 0.58, 0.30]
    w, gap = 96, 54
    x = (S - (len(hs) * w + (len(hs) - 1) * gap)) / 2
    for h in hs:
        hh = 560 * h
        d.rounded_rectangle((x, S / 2 - hh / 2, x + w, S / 2 + hh / 2), radius=w / 2, fill=255)
        x += w + gap
    img.paste(lin_grad((45, 212, 191), (96, 165, 250), 90), (0, 0), bars)
    return img


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    icon = draw_icon()
    icon.save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
    print("ok", OUT)
