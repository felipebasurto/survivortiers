"""Convierte sprites/*.png (y sprites/shiny/*.png) en .webp sin pérdida (pixel art: mismo dibujo, ~4 veces menos).
Necesita Pillow. Solo hace falta al añadir o cambiar sprites; los .webp van en el repositorio y jsDelivr los sirve."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
for png in sorted((ROOT / "sprites").rglob("*.png")):
    out = png.with_suffix(".webp")
    if not out.exists() or out.stat().st_mtime < png.stat().st_mtime:
        Image.open(png).save(out, "WEBP", lossless=True, method=6, quality=100)
