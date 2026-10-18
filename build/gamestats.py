"""Datos del juego que leen el buscador por tipos y el planificador de build, en el commit que fija data/game_stats.json
(build/export_game_stats.js): si cada movimiento es físico o especial, qué potenciador sube qué, el daño de ataque
físico y especial (pa, sa) de cada Pokémon y la tabla de tipos de una sola vez.

Los textos que citan el juego se refieren a ese mismo commit, así que la cita se construye desde COMMIT.
"""
from __future__ import annotations

import json
from pathlib import Path

import legal
from i18n import TYPE_NAMES

DATA = Path(__file__).resolve().parent.parent / "data"
GAME = json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))
MOVE_ICONS = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
TYPE_MATRIX = json.loads((DATA / "type_matrix.json").read_text(encoding="utf8"))

COMMIT = GAME["commit"]
TYPE_KEYS = tuple(TYPE_NAMES["es"])
DANCE_IDS = ("swords-dance", "dragon-dance")  # las dos de ataque físico: comparten casilla de potenciador
BOOST_ORDER = ("swords-dance", "dragon-dance", "nasty-plot", "agility", "harden", "aqua-ring")
CAT_OF_STAT = {"patk": "physical", "satk": "special"}


def game_url(path: str) -> str:
    return f"{legal.GAME_REPO_URL}/blob/{COMMIT}/{path}"


def move(move_id: str) -> dict:
    return GAME["moves"][move_id]


def cat(move_id: str) -> str | None:
    return GAME["moves"][move_id]["cat"]


def side_of(dex: int) -> str:
    """Lado fuerte del Pokémon, igual que G.Stats.sideOf: especial solo si su ataque especial es mayor."""
    pa, sa, _, _ = GAME["dex"][str(dex)]
    return "special" if sa > pa else "physical"


def single_chart() -> dict[str, dict[str, float]]:
    return {atk: {d: TYPE_MATRIX[atk][d] for d in TYPE_KEYS} for atk in TYPE_KEYS}


def site_json() -> dict:
    moves = {}
    for mid, m in GAME["moves"].items():
        entry = {"n": [m["name"], m["en"]], "t": m["type"], "c": m["cat"]}
        if "buff" in m:
            entry["b"] = m["buff"]
        if mid in MOVE_ICONS:
            entry["i"] = MOVE_ICONS[mid]
        moves[mid] = entry
    return {"commit": COMMIT, "chart": single_chart(), "moves": moves, "pool": GAME["pool"], "dex": GAME["dex"]}
