"""Datos de movimientos que vienen del juego (JPTER78/pokesurvivor) y no del análisis de ataques.

La categoría física o especial sale de data/game_stats.json (build/export_game_stats.js, commit GAME_REF), que
la lee de js/data/moves.js:620-630. Los textos y el potenciador sin puesto sí están copiados a mano de ese commit.
"""
from __future__ import annotations

import json
from pathlib import Path

GAME_REF = "5a23d49"

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
# levelup.js:46-49 (recuento de los de tipo buff) y :56 (se quitan de la oferta de movimientos nuevos; las mejoras no).
_CAP_ES = "Con dos potenciadores, las cartas de movimiento nuevo ya no ofrecen más."
_CAP_EN = "With two boosts, new-move cards stop offering more."
NOTES = {
    "swords-dance": (
        "Solo sube el ataque físico. Dura 7 s y comparte contador con Danza Dragón: no se suman. "
        "Si tu Pokémon pega especial, usa Maquinación. " + _CAP_ES,
        "Only raises physical attack. Lasts 7 s and shares its counter with Dragon Dance: they don't add up. "
        "If your Pokémon attacks with special moves, use Nasty Plot. " + _CAP_EN,
    ),
    "dragon-dance": (
        "Solo sube el ataque físico. Dura 7 s y comparte contador con Danza Espada: no se suman. "
        "Si tu Pokémon pega especial, usa Maquinación. " + _CAP_ES,
        "Only raises physical attack. Lasts 7 s and shares its counter with Swords Dance: they don't add up. "
        "If your Pokémon attacks with special moves, use Nasty Plot. " + _CAP_EN,
    ),
}

# js/data/moves.js:196 (Maquinación, en 5a23d49). No tiene puesto en la tier list de potenciadores, que sale del
# análisis anterior y no la midió; la búsqueda de grupos sí la prueba.
# Sus cifras son las base del juego, sin mejoras de nivel.
UNRANKED = [
    {
        "id": "nasty-plot", "name": ("Maquinación", "Nasty Plot"), "type": "normal", "kind": "buff",
        "stat": ("ataque especial", "special attack"), "amount": 0.13, "stacks": 5, "dur": 7, "cd": 0.85,
        "note": (
            "Solo sube el ataque especial. Dura 7 s y tiene su propio contador, así que puedes llevarla con una danza física. "
            "Es para los atacantes especiales. " + _CAP_ES,
            "Only raises special attack. Lasts 7 s and has its own counter, so you can run it with a physical dance. "
            "It is for special attackers. " + _CAP_EN,
        ),
    },
]
