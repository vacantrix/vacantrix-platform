"""Генерация иконок приложений для инструментов платформы."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "resources"
SIZE = 512


# ── Helpers ───────────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def _rounded_base(color_top, color_bot, radius: int = 80) -> Image.Image:
    """Градиентный фон с закруглёнными углами."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # Рисуем вертикальный градиент
    grad = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        t = y / SIZE
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        ImageDraw.Draw(grad).line([(0, y), (SIZE, y)], fill=(r, g, b, 255))
    # Маска скруглённых углов
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1],
                                            radius=radius, fill=255)
    img.paste(grad, mask=mask)
    return img


def _circle_filled(cx, cy, r, color, alpha=255) -> Image.Image:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r],
                                  fill=(*color, alpha))
    return layer


def _glow(layer: Image.Image, radius: int) -> Image.Image:
    return layer.filter(ImageFilter.GaussianBlur(radius))


def _draw_text_centered(img: Image.Image, text: str, font, color,
                        cx: int, cy: int, alpha: int = 255):
    d = ImageDraw.Draw(img)
    d.text((cx, cy), text, font=font, fill=(*color, alpha), anchor="mm")


# ── AVITO ICON ────────────────────────────────────────────────────────────────
# Стиль: тёмный фон → крупный зелёный круг-значок (бренд Avito) → белая «А»

def make_avito_icon() -> Image.Image:
    GREEN  = (0, 200, 100)     # Avito green
    GREEN2 = (0, 160, 75)      # чуть темнее для градиента круга
    WHITE  = (255, 255, 255)
    BG_TOP = (8, 20, 12)
    BG_BOT = (4, 10, 6)

    img = _rounded_base(BG_TOP, BG_BOT, radius=88)
    cx = cy = SIZE // 2

    # ── Glow-аура под кругом ──────────────────────────────────────────────────
    aura_r = 185
    for blur, alpha in [(55, 60), (35, 100), (18, 60)]:
        aura = _circle_filled(cx, cy, aura_r, GREEN, alpha)
        img.alpha_composite(_glow(aura, blur))

    # ── Заливка круга (градиент top→bot) ──────────────────────────────────────
    circle_r = 165
    circle_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for dy in range(-circle_r, circle_r + 1):
        chord = int(math.sqrt(max(0, circle_r**2 - dy**2)))
        t = (dy + circle_r) / (2 * circle_r)
        cr = int(GREEN[0] + (GREEN2[0] - GREEN[0]) * t)
        cg = int(GREEN[1] + (GREEN2[1] - GREEN[1]) * t)
        cb = int(GREEN[2] + (GREEN2[2] - GREEN[2]) * t)
        x0, x1 = cx - chord, cx + chord
        y = cy + dy
        if 0 <= y < SIZE:
            ImageDraw.Draw(circle_layer).line([(x0, y), (x1, y)],
                                              fill=(cr, cg, cb, 255))
    # маска-круг
    cmask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(cmask).ellipse(
        [cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r], fill=255
    )
    circle_layer.putalpha(cmask)
    img.alpha_composite(circle_layer)

    # ── Световой блик сверху-слева (объём) ────────────────────────────────────
    hi = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(hi).ellipse(
        [cx - circle_r + 18, cy - circle_r + 18,
         cx + 30, cy + 30], fill=(255, 255, 255, 38)
    )
    img.alpha_composite(_glow(hi, 20))

    # ── Белая буква «А» ───────────────────────────────────────────────────────
    f_big = _font(240)
    # Тень
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((cx + 5, cy + 18), "А", font=f_big,
                                fill=(0, 0, 0, 120), anchor="mm")
    img.alpha_composite(_glow(shadow, 6))
    # Буква
    _draw_text_centered(img, "А", f_big, WHITE, cx, cy + 10)

    # ── Надпись «АВИТО» снизу тёмным текстом ─────────────────────────────────
    # Белая строка поверх тёмного фона
    f_sub = _font(54)
    label_y = SIZE - 60
    # Лёгкая тёмная подложка
    pill = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle(
        [cx - 100, label_y - 26, cx + 100, label_y + 28], radius=16,
        fill=(0, 0, 0, 100)
    )
    img.alpha_composite(pill)
    _draw_text_centered(img, "АВИТО", f_sub, WHITE, cx, label_y, alpha=230)

    return img


# ── HH.RU ICON ────────────────────────────────────────────────────────────────
# Стиль: тёмно-красный фон → крупные белые буквы «hh» → красный акцент «.ru»

def make_hh_icon() -> Image.Image:
    RED    = (220, 40, 40)    # HH brand red
    RED2   = (170, 20, 20)
    WHITE  = (255, 255, 255)
    BG_TOP = (22, 5, 5)
    BG_BOT = (10, 2, 2)

    img = _rounded_base(BG_TOP, BG_BOT, radius=88)
    cx = cy = SIZE // 2

    # ── Фоновое свечение ──────────────────────────────────────────────────────
    for blur, alpha in [(80, 55), (50, 90), (28, 50)]:
        aura = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        ImageDraw.Draw(aura).ellipse(
            [cx - 190, cy - 150, cx + 190, cy + 150], fill=(*RED2, alpha)
        )
        img.alpha_composite(_glow(aura, blur))

    # ── Большие белые «hh» ────────────────────────────────────────────────────
    f_hh = _font(260)
    # Красная тень → придаёт объём
    for dx, dy, al in [(6, 8, 80), (3, 4, 120)]:
        sh = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((cx + dx, cy - 28 + dy), "hh", font=f_hh,
                                fill=(*RED2, al), anchor="mm")
        img.alpha_composite(_glow(sh, 8))
    _draw_text_centered(img, "hh", f_hh, WHITE, cx, cy - 28, alpha=255)

    # ── Красная полоса-подчёркивание ──────────────────────────────────────────
    bar_y = cy + 115
    bar = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle(
        [cx - 155, bar_y - 6, cx + 155, bar_y + 6], radius=6, fill=(*RED, 255)
    )
    img.alpha_composite(_glow(bar, 10))
    ImageDraw.Draw(img).rounded_rectangle(
        [cx - 155, bar_y - 4, cx + 155, bar_y + 4], radius=4, fill=(*RED, 230)
    )

    # ── «.ru» снизу красным ───────────────────────────────────────────────────
    f_ru = _font(72)
    _draw_text_centered(img, ".ru", f_ru, RED, cx, SIZE - 65, alpha=240)

    # ── Лёгкий блик сверху ────────────────────────────────────────────────────
    hi = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(hi).rounded_rectangle(
        [40, 14, SIZE - 40, SIZE // 3], radius=60, fill=(255, 255, 255, 14)
    )
    img.alpha_composite(_glow(hi, 18))

    return img


# ── Render ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    avito = make_avito_icon()
    avito.save(OUT / "avito_icon.png", "PNG")
    print("OK:", OUT / "avito_icon.png")

    hh = make_hh_icon()
    hh.save(OUT / "hh_icon.png", "PNG")
    print("OK:", OUT / "hh_icon.png")
