"""Marca de PokéSurvivor Tiers: una lista de tiers en una rejilla de 16 × 16 píxeles.

Tres filas, cada una con una ficha del color de su tier (S, A, B) y una barra clara que baja.
Se dibuja con píxeles enteros, como la fuente del sitio.
    python3 build/brand_mark.py   # escribe src/brand/ (mark.svg, favicon.ico, apple-touch-icon.png)
render.py copia esos archivos a la raíz de site/.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "brand"

GRID = 16
BADGE = (44, 81, 159)      # --accent del modo claro: se ve sobre fondo claro y oscuro
BAR = (238, 244, 255)      # --bg del modo claro
TIERS = ((255, 92, 92), (255, 159, 67), (255, 217, 61))  # --tier-S, --tier-A, --tier-B
BAR_WIDTHS = (6, 5, 4)     # en píxeles de la rejilla, de la ficha hacia la derecha
ROW_Y = (3, 7, 11)         # fila de 3 píxeles con 1 de hueco
CHIP_X, CHIP_W = 3, 3

# Octágono de píxeles: las cuatro esquinas quitan un píxel, sin curvas.
BADGE_PATH = [(1, 0), (15, 0), (15, 1), (16, 1), (16, 15), (15, 15), (15, 16), (1, 16),
              (1, 15), (0, 15), (0, 1), (1, 1)]


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def rects() -> list[tuple[int, int, int, int, tuple[int, int, int]]]:
    """Rectángulos (x, y, ancho, alto, color) de la marca, en píxeles de la rejilla."""
    out = []
    for y, tier, w in zip(ROW_Y, TIERS, BAR_WIDTHS):
        out.append((CHIP_X, y, CHIP_W, 3, tier))
        out.append((CHIP_X + CHIP_W + 1, y, w, 3, BAR))
    return out


def svg() -> str:
    body = [f'<path fill="{_hex(BADGE)}" d="M1 0H15V1H16V15H15V16H1V15H0V1H1Z"/>']
    for x, y, w, h, color in rects():
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{_hex(color)}"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">'
            + "".join(body) + "</svg>\n")


def draw(d: ImageDraw.ImageDraw, x: float, y: float, unit: float) -> None:
    """Dibuja la marca en (x, y) con `unit` píxeles por celda."""
    pts = [(x + px * unit, y + py * unit) for px, py in BADGE_PATH]
    d.polygon(pts, fill=BADGE)
    for rx, ry, w, h, color in rects():
        d.rectangle([x + rx * unit, y + ry * unit, x + (rx + w) * unit - 1, y + (ry + h) * unit - 1], fill=color)


def image(px: int) -> Image.Image:
    """La marca como RGBA de px × px. Se dibuja a 64 píxeles por celda y se reduce con BOX, así las celdas quedan nítidas."""
    big = 64
    canvas = Image.new("RGBA", (GRID * big, GRID * big), (0, 0, 0, 0))
    draw(ImageDraw.Draw(canvas), 0, 0, big)
    return canvas.resize((px, px), Image.BOX)


def ico_bytes(sizes: tuple[int, ...]) -> bytes:
    """Un .ico con un PNG por tamaño. PIL reduce con LANCZOS y emborronaría los píxeles; aquí cada tamaño sale exacto."""
    pngs = []
    for px in sizes:
        buf = io.BytesIO()
        image(px).save(buf, format="PNG", optimize=True)
        pngs.append(buf.getvalue())
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for px, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", px % 256, px % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(pngs)


def write_assets(out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    svg_path = out_dir / "mark.svg"
    svg_path.write_text(svg(), encoding="utf8")
    written.append(svg_path)
    ico_path = out_dir / "favicon.ico"
    ico_path.write_bytes(ico_bytes((16, 32)))
    written.append(ico_path)
    apple_path = out_dir / "apple-touch-icon.png"
    image(180).save(apple_path, optimize=True)
    written.append(apple_path)
    return written


def main() -> int:
    for path in write_assets():
        print(f"brand: {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
