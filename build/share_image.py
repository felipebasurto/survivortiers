"""Imagen para compartir (og:image y twitter:image), 1200 × 630, en build/assets/og.png.

Se dibuja con la fuente pixel del sitio (src/fonts, OFL), la marca de build/brand_mark.py y las primeras fichas S del ranking, como cartas de gacha.
    python3 build/share_image.py      # render.py la copia a site/og.png
"""
from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand_mark

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "src" / "fonts" / "PixelifySans.ttf"
RANKING = ROOT / "data" / "ranking_definitive.csv"
SPRITES = ROOT / "sprites"
OUT = ROOT / "build" / "assets" / "og.png"

W, H = 1200, 630
BG = (11, 24, 56)          # --ink del modo claro: un azul más oscuro que la marca
INK = (255, 255, 255)      # --ink del modo oscuro
MUTED = (195, 212, 245)    # --ink-2 del modo oscuro
ACCENT = (255, 210, 63)    # --accent del modo oscuro
CARD = (20, 38, 90)        # --bg del modo oscuro
TIER = {"S": (255, 92, 92), "A": (255, 159, 67), "B": (255, 217, 61), "C": (107, 203, 119), "D": (77, 150, 255)}
TIER_INK = (11, 24, 56)
S_CARDS = 9


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def fit_font(text: str, max_w: int, start: int) -> ImageFont.FreeTypeFont:
    """La fuente más grande (hasta start) con la que text cabe en max_w píxeles."""
    size = start
    while size > 20 and font(size).getlength(text) > max_w:
        size -= 2
    return font(size)


def s_tier_rows() -> list[dict]:
    lines = [l for l in RANKING.read_text(encoding="utf8").splitlines() if not l.startswith("#")]
    rows = list(csv.DictReader(lines))
    return [r for r in rows if r["tier"] == "S"][:S_CARDS]


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, 40):
        gd.line([(x, 0), (x, H)], fill=(238, 244, 255, 14))
    for y in range(0, H, 40):
        gd.line([(0, y), (W, y)], fill=(238, 244, 255, 14))
    img.paste(grid, (0, 0), grid)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([720, -160, 1280, 400], fill=(255, 92, 92, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    img.paste(glow, (0, 0), glow)
    return img


def text(d: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, f: ImageFont.FreeTypeFont, fill) -> None:
    d.text(xy, s, font=f, fill=fill)


def card(img: Image.Image, x: int, y: int, size: int, row: dict, rank: int) -> None:
    """Una carta de gacha: marco del color de su tier, sprite de pixel art sin suavizar, número y nombre."""
    d = ImageDraw.Draw(img)
    color = TIER[row["tier"]]
    d.rounded_rectangle([x, y, x + size, y + size], radius=18, fill=CARD, outline=color, width=5)
    # brillo diagonal de carta de gacha
    shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shine).polygon([(x + 10, y + 60), (x + 60, y + 10), (x + 90, y + 10), (x + 10, y + 90)],
                                  fill=(255, 255, 255, 34))
    img.paste(shine, (0, 0), shine)
    sprite = Image.open(SPRITES / f"{row['dex']}.png").convert("RGBA")
    box = size - 64
    scale = min(box / sprite.width, box / sprite.height)
    sprite = sprite.resize((max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))), Image.NEAREST)
    img.paste(sprite, (x + (size - sprite.width) // 2, y + 20 + (box - sprite.height) // 2), sprite)
    d = ImageDraw.Draw(img)
    badge = font(22)
    d.rounded_rectangle([x + 8, y + 8, x + 44, y + 40], radius=8, fill=color)
    d.text((x + 26, y + 24), str(rank), font=badge, fill=TIER_INK, anchor="mm")
    name = row["name"]
    nf = fit_font(name, size - 16, 22)
    d.text((x + size // 2, y + size - 16), name, font=nf, fill=INK, anchor="mm")


def build() -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    # columna izquierda: marca, nombre y chips de tier
    unit = 8
    brand_mark.draw(d, 72, 64, unit)
    line = fit_font("Survivor", 500, 112)
    text(d, (66, 218), "Survivor", line, INK)
    text(d, (66, 218 + line.size + 4), "Tiers", line, ACCENT)
    text(d, (72, 446), "Tier list no oficial de PokéSurvivor", font(32), INK)
    text(d, (72, 490), "Unofficial PokéSurvivor tier list", font(24), MUTED)
    x = 72
    for tier in "SABCD":
        d.rounded_rectangle([x, 528, x + 64, 580], radius=12, fill=TIER[tier])
        d.text((x + 32, 554), tier, font=font(36), fill=TIER_INK, anchor="mm")
        x += 64 + 12
    text(d, (72, 600), "966 Pokémon · survivortiers.pages.dev", font(22), MUTED)
    # cartas S a la derecha
    size, gap = 150, 14
    x0 = 1150 - (3 * size + 2 * gap)
    y0 = (H - (3 * size + 2 * gap)) // 2
    for i, row in enumerate(s_tier_rows()):
        cx = x0 + (i % 3) * (size + gap)
        cy = y0 + (i // 3) * (size + gap)
        card(img, cx, cy, size, row, i + 1)
    return img.convert("RGB")


def save(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    build().save(path, optimize=True)


def main() -> int:
    save(OUT)
    print(f"share image: {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
