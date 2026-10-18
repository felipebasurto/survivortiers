"""Datos de movimientos que vienen del juego (JPTER78/pokesurvivor) y no del análisis de ataques.

La categoría física o especial sale de data/game_stats.json (build/export_game_stats.js, commit GAME_REF), que
la lee de js/data/moves.js:429-435. Los textos y el potenciador sin puesto sí están copiados a mano de ese commit.
"""
from __future__ import annotations

import json
from pathlib import Path

GAME_REF = "e868b5e"

_GAME_STATS = json.loads((Path(__file__).resolve().parent.parent / "data" / "game_stats.json").read_text(encoding="utf8"))

DAMAGE_CLASSES = ("physical", "special", "status")


def damage_class(move_id: str, kind: str) -> str:
    """Los potenciadores (kind buff) no hacen daño: son de estado. El resto es físico o especial, según el juego."""
    if kind == "buff":
        return "status"
    return "physical" if _GAME_STATS["moves"][move_id]["cat"] == "physical" else "special"


def physical_ids() -> frozenset[str]:
    return frozenset(mid for mid, m in _GAME_STATS["moves"].items() if m["cat"] == "physical")


# Textos de los potenciadores de la tier list. Cada uno es una pareja (es, en). El límite de dos potenciadores es
# levelup.js:47-49 (recuento) y :56 (se quitan de la oferta de cartas).
_CAP_ES = "Con dos potenciadores de cualquier tipo, ya no salen más."
_CAP_EN = "With two boosts of any kind, no more come up."
NOTES = {
    "swords-dance": (
        "Solo sube el ataque físico. Si tu Pokémon pega físico, usa esta; si pega especial, Maquinación. " + _CAP_ES,
        "Only raises physical attack. If your Pokémon attacks physically, use this one; if it attacks with special "
        "moves, use Nasty Plot. " + _CAP_EN,
    ),
    "dragon-dance": (
        "Solo sube el ataque físico. Si tu Pokémon pega físico, usa esta; si pega especial, Maquinación. " + _CAP_ES,
        "Only raises physical attack. If your Pokémon attacks physically, use this one; if it attacks with special "
        "moves, use Nasty Plot. " + _CAP_EN,
    ),
}

# js/data/moves.js:139-141 (Maquinación, en e868b5e). Es nueva y todavía no tiene puesto: la simulación del ranking
# no la ha medido, así que no lleva tier ni valor. Sus cifras son las base del juego, sin mejoras de nivel.
UNRANKED = [
    {
        "id": "nasty-plot", "name": ("Maquinación", "Nasty Plot"), "type": "normal", "kind": "buff",
        "stat": ("ataque especial", "special attack"), "amount": 0.13, "stacks": 5, "dur": 7, "cd": 0.85,
        "note": (
            "Solo sube el ataque especial. Es para los atacantes especiales; los físicos usan Danza Espada. " + _CAP_ES,
            "Only raises special attack. It is for special attackers; physical ones use Swords Dance. " + _CAP_EN,
        ),
    },
]
