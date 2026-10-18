"""Cartas de subida de nivel de cada Pokémon, para la tarjeta Build, el planificador, la ficha estática y la FAQ.

Dos lecturas de data/passive_sim.json:

- `priority` (la que se muestra): las 8 cartas de estadística en el orden del banco de monedas de cada especie
  (`order`, la mediana de monedas cuando esa estadística va primero; ver simulator/card_priority.py), de mejor a peor,
  y aparte la carta `needs` del ataque que abre el grupo, que hace falta una vez para evolucionarlo.
- `compute` (la que usa el resumen de la ficha): lo que el bot coge en una partida. pick_card
  (simulator/sim-rs/src/engine.rs) coge la carta de evolución una sola vez y después apila solo la mejor del banco,
  así que no es una lista de prioridades. Los textos de summaries.json se validan contra esta función: no la cambies
  sin rehacer los resúmenes.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
STATS = ("atk", "spd", "hp", "def", "cd", "rgn", "mag", "xp")


def load() -> dict:
    return json.loads((DATA / "passive_sim.json").read_text(encoding="utf8"))


def priority(dex: int, group_moves: list[str], sim: dict) -> list:
    """[[8 ids de carta, de mejor a peor], id de la carta que evoluciona el ataque principal, o None]."""
    order = sim["order"].get(str(dex))
    if not order or sorted(order) != sorted(STATS):
        raise ValueError(f"{dex}: passive_sim.json no tiene las 8 cartas en orden")
    gate = sim["needs"].get(group_moves[0]) if group_moves else None
    if gate not in STATS:
        gate = None
    return [list(order), gate]


def compute(dex: int, group_moves: list[str], sim: dict) -> list:
    """[[ids], cuántas de las primeras se cogen una sola vez]. Solo para summary_facts y los resúmenes."""
    order = sim["order"].get(str(dex), [])
    if not order:
        return [[], 0]
    stack = order[0]
    gate = sim["needs"].get(group_moves[0]) if group_moves else None
    if gate and gate != stack:
        return [[gate, stack], 1]
    return [[stack], 0]
