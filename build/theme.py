"""Tema claro u oscuro. El script de <head> aplica la elección guardada antes del primer pintado, sin parpadeo. Como la
CSP no admite scripts en línea salvo por huella, su sha256 va en src/_headers y en vercel.json: render.py se niega a
generar el sitio si cambia el script y no se actualizan.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

STORAGE_KEY = "survivortiers.tema"
THEME_COLOR = {"light": "#f6f0dc", "dark": "#1b1528"}  # --bg de cada tema, para la barra del navegador en móvil
INIT_JS = (
    "(function(){var h=document.documentElement,t=null;"
    f"try{{t=localStorage.getItem('{STORAGE_KEY}')}}catch(e){{}}"
    "if(t==='light'||t==='dark')h.dataset.theme=t;"
    "var d=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);"
    f"document.getElementById('theme-color').content=d?'{THEME_COLOR['dark']}':'{THEME_COLOR['light']}'}})();"
)
CSP_FILES = ("src/_headers", "vercel.json")


def csp_hash() -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(INIT_JS.encode("utf8")).digest()).decode("ascii")


def script_tag() -> str:
    return f"<script>{INIT_JS}</script>"


def csp_missing(root: Path) -> list[str]:
    """Archivos de configuración de despliegue cuya CSP no lleva la huella del script actual."""
    return [name for name in CSP_FILES if csp_hash() not in (root / name).read_text(encoding="utf8")]
