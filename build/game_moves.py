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


def shape_key(move: dict) -> str:
    """Clave de `mv_kind_*` que usa ataques.html. Un proyectil que persigue o perfora se nombra por eso,
    no como proyectil. El resto usa su kind (homing, bounce, charge, spin, quake, vortex, shove, stun, …)."""
    kind = move["kind"]
    mech = move.get("mech") or {}
    if kind == "projectile" and mech.get("homing", 0) > 0:
        return "homing"
    if kind == "projectile" and mech.get("pierce", 0) > 0:
        return "pierce"
    return kind


def physical_ids() -> frozenset[str]:
    return frozenset(mid for mid, m in _GAME_STATS["moves"].items() if m["cat"] == "physical")


# Notas de los potenciadores. Cada una es una pareja (es, en). Las reglas de contador (cuántos a la vez y el
# límite de dos) están en pasivas y en el planificador, no aquí. Contadores: player.js:42-50 y :99-102, combat.js:201-202.
NOTES = {
    "swords-dance": (
        "Solo sube el ataque físico. Comparte contador con Danza Dragón: no se suman.",
        "Only raises physical attack. Shares its counter with Dragon Dance: they don't add up.",
    ),
    "dragon-dance": (
        "Solo sube el ataque físico. Comparte contador con Danza Espada: no se suman.",
        "Only raises physical attack. Shares its counter with Swords Dance: they don't add up.",
    ),
    "nasty-plot": (
        "Solo sube el ataque especial. Tiene su propio contador: una danza física no lo pisa.",
        "Only raises special attack. It has its own counter: a physical dance doesn't overwrite it.",
    ),
}


# combat.js dash(): cada embestida deja al jugador invulnerable este tiempo (pl.invuln = max(pl.invuln, 0.3)).
DASH_INVULN = 0.3


def dash_cooldowns(mid: str) -> tuple[float, float]:
    """Recarga de una embestida al nivel 1 y al máximo (v3_data.json), en segundos."""
    import coverage
    levels = coverage._v3()["moves"][mid]["levels"]
    return levels[0]["cd"], levels[-1]["cd"]
