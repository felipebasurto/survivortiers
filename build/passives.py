"""Cartas de subida de nivel a priorizar por Pokémon (hasta cuatro), para la tarjeta Build.

1. Primero, las cartas que hacen falta para evolucionar los ataques del grupo: en el juego un ataque al nivel máximo
   solo evoluciona después de coger una vez la carta de su condición (`needs`; js/data/moves.js evoInfo y
   js/systems/levelup.js, cartas de evolución).
2. Después, las de estadística por lo que aguantó el bot de grupo fijo (simulator/, --group 2+2) cuando esa carta iba
   primera (data/passive_sim.json, 40 partidas por orden; estimación).
3. Como mucho una carta de aguante (Síntesis `rgn` o Vigor `hp`) entre las de estadística: el bot no esquiva como una
   persona, así que la curación y la vida máxima salen sobrevaloradas en la sim aunque ya modela jefes y bayas de
   curación (js/systems/pickup.js:81,93; js/game.js:463). La segunda baja al final.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MAX_CARDS = 4
SUSTAIN = {"rgn", "hp"}


def load() -> dict:
    return json.loads((DATA / "passive_sim.json").read_text(encoding="utf8"))


def compute(dex: int, group_moves: list[str], sim: dict) -> list:
    """[[ids de carta], cuántas de las primeras son de evolución]."""
    evo = []
    for m in group_moves:
        need = sim["needs"].get(m)
        if need and need not in evo:
            evo.append(need)
    evo = evo[:MAX_CARDS]
    rest = [c for c in sim["order"].get(str(dex), []) if c not in evo]
    sustain = [c for c in rest if c in SUSTAIN]
    if len(sustain) > 1 or (sustain and any(c in SUSTAIN for c in evo)):
        keep = set() if any(c in SUSTAIN for c in evo) else {sustain[0]}
        rest = [c for c in rest if c not in SUSTAIN or c in keep] + [c for c in rest if c in SUSTAIN and c not in keep]
    return [evo + rest[:MAX_CARDS - len(evo)], len(evo)]
