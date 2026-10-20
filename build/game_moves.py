"""Datos de movimientos que vienen del juego (JPTER78/pokesurvivor) y no del análisis de ataques.

La categoría física o especial sale de data/game_stats.json (build/export_game_stats.js, commit GAME_REF), que
la lee de js/data/moves.js:620-630. Las notas de los potenciadores sí están escritas a mano sobre ese commit.
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


def attack_class(move_id: str) -> str:
    """Categoría de daño de un movimiento del juego: physical, special o status."""
    info = _GAME_STATS["moves"][move_id]
    return damage_class(move_id, info["kind"])


def physical_ids() -> frozenset[str]:
    return frozenset(mid for mid, m in _GAME_STATS["moves"].items() if m["cat"] == "physical")


# Notas de los potenciadores. Cada una es una pareja (es, en). El límite de dos potenciadores es levelup.js:46-49
# (recuento de los de tipo buff) y :56 (se quitan de la oferta de movimientos nuevos; las mejoras no). Los contadores
# de ataque físico (patk) y especial (satk): player.js:42-50 y :99-102, combat.js:201-202.
_CAP_ES = "Con dos potenciadores, las cartas de movimiento nuevo ya no ofrecen más."
_CAP_EN = "With two boosts, new-move cards stop offering more."
NOTES = {
    "swords-dance": (
        "Solo sube el ataque físico y comparte contador con Danza Dragón: no se suman. " + _CAP_ES,
        "Only raises physical attack and shares its counter with Dragon Dance: they don't add up. " + _CAP_EN,
    ),
    "dragon-dance": (
        "Solo sube el ataque físico y comparte contador con Danza Espada: no se suman. " + _CAP_ES,
        "Only raises physical attack and shares its counter with Swords Dance: they don't add up. " + _CAP_EN,
    ),
    "nasty-plot": (
        "Solo sube el ataque especial y tiene su propio contador: una danza física no lo pisa. " + _CAP_ES,
        "Only raises special attack and has its own counter: a physical dance doesn't overwrite it. " + _CAP_EN,
    ),
}
