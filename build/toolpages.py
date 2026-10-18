"""Rutas de las dos herramientas (buscador por tipos y planificador de build) en cada idioma. El menú las pide con
«@finder» o «@planner» en lugar de un nombre de archivo, porque el nombre cambia entre español e inglés.
"""
from __future__ import annotations

import json

import legal
import typedata
from i18n import TYPE_NAMES, Lang

FOLDERS = {
    "finder": {"es": "buscador-tipos/", "en": "type-finder/"},
    "planner": {"es": "planificador-build/", "en": "build-planner/"},
}


def folder(L: Lang, key: str) -> str:
    return FOLDERS[key]["en" if L.en else "es"]


def rel(L: Lang, key: str) -> str:
    return folder(L, key) + "index.html"


def twin(L: Lang, key: str) -> str:
    """La misma página en el otro idioma, relativa a la raíz de su idioma (la que pide Ctx.of como twin)."""
    other = "es" if L.en else "en"
    return FOLDERS[key][other] + "index.html"


def target(L: Lang, href: str) -> str:
    if href.startswith("@"):
        return folder(L, href[1:])
    return href


def pairs() -> list[tuple[str, str]]:
    """(ruta en español, ruta en inglés) de cada herramienta, con la barra final, como las páginas de agents.sitemap."""
    return [(FOLDERS[key]["es"], FOLDERS[key]["en"]) for key in FOLDERS]


def blob(L: Lang, keys: tuple[str, ...]) -> str:
    """Datos que tools.js necesita: textos (con sus marcadores), nombres y colores de los tipos. Va como JSON que no
    se ejecuta, igual que #i18n de la ficha."""
    names = TYPE_NAMES[L.code]
    types = {t: {"n": names[t], "c": typedata.TYPE_COLOR[t], "tc": typedata.text_color(t), "g": typedata.glyph_svg(t)}
             for t in typedata.TYPE_COLOR}
    strings = {k: L.t_raw(k).replace("{game}", legal.GAME_NAME).replace("{site}", legal.SITE_NAME) for k in keys}
    text = json.dumps({"en": L.en, "s": strings, "types": types}, ensure_ascii=False)
    return f'<script type="application/json" id="i18n">{text.replace("</", "<\\/")}</script>'
