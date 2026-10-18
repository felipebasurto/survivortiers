"""Nota de la mejora Repertorio (1.500 Pokémonedas), en una línea y con el icono del juego. La regla sale de js/data/upgrades.js:15
(id moves, icon cards) y de js/game.js:140-144 (la segunda carta es al azar). El dibujo es UI.cards de js/ui/icons.js:70, a 1:1.
"""
from __future__ import annotations

from html import escape

from i18n import Lang

PALETTE = {"k": "#1b1528", "a": "#ffd23f", "b": "#4fb4ff", "w": "#e6f4ff"}
ROWS = (
    "............", ".kkkkkk.....", ".kaaaaakkkk.", ".kaaaakbbbbk", ".kaaaakbwwbk", ".kaaaakbwwbk",
    ".kaaaakbbbbk", ".kaaaakbwwbk", ".kkkkkkbwwbk", "......kbbbbk", "......kkkkkk", "............",
)


def _icon() -> str:
    rects = []
    for y, row in enumerate(ROWS):
        x = 0
        while x < len(row):
            ch = row[x]
            if ch == ".":
                x += 1
                continue
            n = 1
            while x + n < len(row) and row[x + n] == ch:
                n += 1
            rects.append(f'<rect x="{x}" y="{y}" width="{n}" height="1" fill="{PALETTE[ch]}"/>')
            x += n
    return (f'<svg class="rep-ico" viewBox="0 0 12 12" aria-hidden="true" focusable="false" '
            f'shape-rendering="crispEdges">{"".join(rects)}</svg>')


ICON = _icon()


def note(L: Lang) -> str:
    return f'<p class="rep-note">{ICON}<span>{escape(L.t("rep_note"), quote=False)}</span></p>'
