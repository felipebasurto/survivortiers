"""Por qué casi todo tier S es de tipo Acero: la nota bajo la cabecera S de la tier list y la pregunta de Método.

Todas las cifras salen de los datos del build: la build que muestra la tarjeta de cada Pokémon de tier S
(ranking_fase3.csv y species_builds.csv, en `entries`), sus tipos (pokedex_export.json), la tabla de ataques de la
fase 1 (attack_tiers.csv, en `moves`), los números del ataque en v3_data.json y qué tipos lo aprenden según
data/move_pool.json. `compute` no escribe nada: devuelve `show: False` si la nota no se sostiene, es decir, si los
Acero no son al menos la mitad de tier S, si Puño Meteoro no es el primer ataque físico de la fase 1 o si lo
aprende algún tipo que no sea Acero.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL_JSON = ROOT / "data" / "move_pool.json"
COMBAT_JS = ROOT / "simulator" / "vendor" / "pokesurvivor-5a23d49" / "js" / "systems" / "combat.js"

TIER = "S"
TYPE = "steel"
MOVE_ID = "meteor-mash"
# combat.js, reach(): los meteoros caen sobre enemigos a esta distancia del Pokémon. No viene en los datos exportados;
# test_tier_s_note.py lo compara con el código del juego vendido.
REACH = 340
_GAME_REACH = re.compile(r"if \(m\.kind === 'meteor'\) return (\d+);")


class TierSError(RuntimeError):
    pass


def game_reach() -> int | None:
    """El alcance de los meteoros en el código del juego vendido, o None si no está en el repositorio."""
    if not COMBAT_JS.exists():
        return None
    found = _GAME_REACH.search(COMBAT_JS.read_text(encoding="utf8"))
    return int(found.group(1)) if found else None


def compute(entries: list[dict], moves: list[dict], v3_moves: dict, pool: dict[str, list[str]]) -> dict:
    """Las cifras de la nota y su condición. `entries` es la lista de catalog.load_pokemon, `moves` la de load_moves."""
    top = [e for e in entries if e["r"]["tier"] == TIER]
    if not top:
        raise TierSError("ningún Pokémon en tier S")
    steel = sum(TYPE in e["types"] for e in top)
    meteor = sum(MOVE_ID in e["builds"][e["r"]["best"]]["moves"] for e in top)
    by_id = {m["id"]: m for m in moves}
    move = by_id.get(MOVE_ID)
    if move is None:
        raise TierSError(f"{MOVE_ID} no está en la tabla de ataques de la fase 1")
    physical = [m["id"] for m in sorted((m for m in moves if m["category"] == "physical"), key=lambda m: m["rank"])]
    phys_rank = physical.index(MOVE_ID) + 1
    learners = sorted(t for t, ids in pool.items() if MOVE_ID in ids)
    game = v3_moves[MOVE_ID]["levels"][0]
    show = steel * 2 >= len(top) and phys_rank == 1 and learners == [TYPE] and meteor > 0
    return {
        "show": show,
        "tier": TIER,
        "n": len(top),
        "steel": steel,
        "meteor": meteor,
        "move": {"id": MOVE_ID, "type": move["type"], "rank": phys_rank,
                 "name": {"es": move["name"], "en": move["en"]["name"]}},
        "learners": learners,
        "stats": {"count": game["count"], "dmg": game["dmg"], "cd": game["cd"], "radius": game["radius"],
                  "knock": game["knock"], "reach": REACH},
    }


def load_pool() -> dict[str, list[str]]:
    return json.loads(POOL_JSON.read_text(encoding="utf8"))
