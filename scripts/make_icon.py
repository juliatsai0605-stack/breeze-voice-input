"""產生 App 圖示：assets/icon.png（1024）與 assets/icon.ico（16～256 多尺寸）。
python scripts/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).resolve().parent.parent / "assets"


def gradient(size, c1, c2):
    """左上 → 右下的對角漸層"""
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return g


def draw_icon(size=S, status_color=None):
    k = size / S
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 背景：圓角方塊＋柔和陰影
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((70 * k, 96 * k, 954 * k, 980 * k), radius=220 * k, fill=(0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28 * k)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((64 * k, 64 * k, 960 * k, 960 * k), radius=220 * k, fill=255)
    bg = gradient(size, (20, 184, 166), (37, 99, 235)).convert("RGBA")
    img.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(img)
    W = (255, 255, 255, 255)
    cx = 400 * k
    # 麥克風頭
    d.rounded_rectangle((cx - 105 * k, 230 * k, cx + 105 * k, 560 * k), radius=105 * k, fill=W)
    # 麥克風架（U 形）
    w = int(46 * k)
    d.arc((cx - 185 * k, 330 * k, cx + 185 * k, 690 * k), 0, 180, fill=W, width=w)
    d.line((cx, 690 * k, cx, 790 * k), fill=W, width=w)
    d.rounded_rectangle((cx - 120 * k, 770 * k, cx + 120 * k, 815 * k), radius=22 * k, fill=W)

    # 聲波弧線（像微風往外擴散），兩端圓角，外圈較淡
    import math
    acx, acy = cx, 395 * k
    lw = 44 * k
    for r, alpha in ((300, 235), (410, 150)):
        col = (255, 255, 255, alpha)
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        R = r * k
        ld.arc((acx - R, acy - R, acx + R, acy + R), -32, 32, fill=col, width=int(lw))
        for ang in (-32, 32):
            a = math.radians(ang)
            mr = R - lw / 2
            ex, ey = acx + mr * math.cos(a), acy + mr * math.sin(a)
            ld.ellipse((ex - lw / 2, ey - lw / 2, ex + lw / 2, ey + lw / 2), fill=col)
        img.alpha_composite(layer)

    if status_color:
        r0 = 300 * k
        d.ellipse((S * k - r0 - 30 * k, S * k - r0 - 30 * k, S * k - 30 * k, S * k - 30 * k),
                  fill=status_color, outline=W, width=int(36 * k))
    return img


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    big = draw_icon()
    big.save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
    # 預覽：大圖＋各小尺寸並排
    prev = Image.new("RGBA", (1024 + 40 + 256, 1024), (245, 245, 245, 255))
    prev.alpha_composite(big)
    y = 20
    for s in (256, 64, 32, 16):
        small = big.resize((s, s), Image.LANCZOS)
        prev.alpha_composite(small, (1064, y)); y += s + 30
    prev.save(OUT / "icon-preview.png")
    print("ok", OUT)
