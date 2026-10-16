"""Cartas de subida de nivel a priorizar por Pokémon (hasta cuatro), para la tarjeta Build.

1. Primero, las cartas que hacen falta para evolucionar los ataques del grupo: en el juego un ataque al nivel máximo
   solo evoluciona después de coger una vez la carta de su condición (`needs`; js/data/moves.js evoInfo y
   js/systems/levelup.js, cartas de evolución).
2. Después, las de estadística por lo que aguantó el bot de grupo fijo (simulator/, --group 2+2) cuando esa carta iba
   primera (data/passive_sim.json, 40 partidas por orden; estimación).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MAX_CARDS = 4


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
    return [evo + rest[:MAX_CARDS - len(evo)], len(evo)]
