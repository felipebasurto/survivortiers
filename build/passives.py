"""Cartas que el bot coge de verdad en una partida, para la tarjeta Build, la ficha que se comparte y la FAQ.

El orden de monedas (data/passive_sim.json) dice qué estadística conviene apilar. No es una lista de
prioridades para ir turnando: pick_card (simulator/sim-rs/src/engine.rs) hace otra cosa.

1. El ataque principal se sube hasta el nivel máximo.
2. Si ese ataque evoluciona, su carta `needs` se coge una sola vez (`stacks < 1`) y enseguida se evoluciona.
   El tope de la carta es otro número (Imán 6, Aprendizaje 8, Carrera 8, Reflejos 10, Coraza 12, Potencia 40;
   Vigor y Síntesis llegan a 250 en la pasada con estado) y no hace que el bot la siga prefiriendo.
3. Los compañeros no fuerzan su carta: solo evolucionan si esa estadística ya está en 1.
4. Con un relleno, Danza Espada y Fortaleza van antes, y después se apila solo esa estadística hasta su tope.
   La mejor del banco de monedas es ese relleno. En 900 s el bot no llega al tope de Vigor ni de Síntesis,
   así que no pasa a la siguiente del ranking.

Por eso la lista son las primeras cartas de estadística, no cuatro prioridades planas: la de evolución del
ataque que abre el grupo, una vez, si no es la que se apila; y la que el bot sigue cogiendo.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load() -> dict:
    return json.loads((DATA / "passive_sim.json").read_text(encoding="utf8"))


def compute(dex: int, group_moves: list[str], sim: dict) -> list:
    """[[ids], cuántas de las primeras se cogen una sola vez].

    La última es la estadística que el bot apila (la mejor del banco de monedas). La primera, si hay dos,
    es la carta de evolución del ataque que abre el grupo, y solo cuando no coincide con la que se apila.
    """
    order = sim["order"].get(str(dex), [])
    if not order:
        return [[], 0]
    stack = order[0]
    gate = sim["needs"].get(group_moves[0]) if group_moves else None
    if gate and gate != stack:
        return [[gate, stack], 1]
    return [[stack], 0]
