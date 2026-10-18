"""Aviso del Repertorio, la mejora de 1.500 Pokémonedas. Lo que dice sale del juego en e868b5e: el precio y el texto de la
mejora en js/data/upgrades.js:15, y la segunda carta, que es al azar y sin potenciadores ni movimientos vetados, en
js/game.js:140-144 (Veto en 138). La ficha lo pone por JavaScript (src/ficha.js) con las mismas frases de #i18n.
"""
from __future__ import annotations

from html import escape

from i18n import Lang

ITEMS = ("rep_b1", "rep_b2", "rep_b3")


def box(L: Lang) -> str:
    items = "".join(f"<li>{escape(L.t(k))}</li>" for k in ITEMS)
    return f'<aside class="rep-warn"><p class="rep-h"><b>{escape(L.t("rep_title"))}</b></p><ul>{items}</ul></aside>'
