#!/usr/bin/env python3
"""Kasane のアイコンを生成する。icon.svg と同じ絵を PIL で描いて PNG に落とす。
使い方: python3 make-icons.py"""
from PIL import Image, ImageDraw

S = 1024                      # 原寸
BG_TOP, BG_BOT = (23, 27, 36), (15, 17, 21)
BLUE, GREEN = (79, 140, 255), (56, 211, 159)
RADIUS = 228                  # 角丸
R, W = 182, 96                # プレートの半径と太さ
CX1, CX2, CY = 404, 620, 512  # 2枚の中心


def ring(center_x, color, alpha):
    """1枚のプレート（リング）を透明レイヤーに描く"""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = [center_x - R, CY - R, center_x + R, CY + R]
    d.ellipse(box, outline=color + (alpha,), width=W)
    return layer


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 背景（上から下へのグラデーション）を角丸でマスク
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)],
                fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], RADIUS, fill=255)
    img.paste(grad, (0, 0), mask)

    # 重ねる2枚。右を少し透かして、重なりが色として見えるようにする
    img.alpha_composite(ring(CX1, BLUE, 255))
    img.alpha_composite(ring(CX2, GREEN, 199))

    del d
    return img


if __name__ == "__main__":
    master = build()
    for size, name in ((512, "icon.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        master.resize((size, size), Image.LANCZOS).save(name)
        print(f"wrote {name} ({size}x{size})")
