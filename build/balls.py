"""Poké Ball de rareza (el dibujo del juego, data/ball_icons.json) como <symbol> SVG para la ficha.

Rareza 1 a 5 = Común, Poco común, Rara, Épica, Legendaria; cada una con su bola, como en el juego.
La ficha la pinta con <svg><use href="#rball-N"/></svg>; estos símbolos van una vez en la plantilla.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
BALLS = json.loads((DATA / "ball_icons.json").read_text(encoding="utf8"))
# Mismo orden que G.Icons.RARITY_BALL del juego: rareza -> id del dibujo.
RARITY_BALL = {1: "ball", 2: "ball2", 3: "ball3", 4: "ballLux", 5: "ball4"}
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"  # rows[y][x] es '.' o la letra de su color en pal
# RARITY_COLOR de systems/gacha.js del juego: color del nombre de cada rareza.
RARITY_COLOR = {1: "#9fb1c9", 2: "#5fe08a", 3: "#4fb4ff", 4: "#c47bff", 5: "#ffcb3d"}


def symbol_id(rarity: int) -> str:
    return f"rball-{rarity}"


def defs() -> str:
    """Un <symbol> por rareza, en rectángulos de píxeles del juego, dentro de un SVG oculto."""
    out = []
    for rarity, ball_id in RARITY_BALL.items():
        ic = BALLS[ball_id]
        w, h = ic["size"]
        rects = []
        for y, row in enumerate(ic["rows"]):
            x = 0
            while x < w:
                ch = row[x]
                if ch == ".":
                    x += 1
                    continue
                run = 1
                while x + run < w and row[x + run] == ch:
                    run += 1
                color = ic["pal"][ICON_LETTERS.index(ch)]
                rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{color}"/>')
                x += run
        out.append(f'<symbol id="{symbol_id(rarity)}" viewBox="0 0 {w} {h}">{"".join(rects)}</symbol>')
    return ('<svg class="sprites-defs" width="0" height="0" aria-hidden="true" focusable="false">'
            + "".join(out) + "</svg>")
