"""Datos de movimientos que vienen del juego (JPTER78/pokesurvivor) y no del análisis de ataques.

Todo lo de aquí está copiado a mano del commit GAME_REF. Si el juego cambia, cambia esto; test_game_moves.py
comprueba que las listas cuadren con los datos del build.
"""
from __future__ import annotations

GAME_REF = "e868b5e"

# js/data/moves.js:429-431 (PHYSICAL). Es la lista completa de ataques físicos. Cualquier otro ataque que hace daño
# es especial (moves.js:435). Los potenciadores (kind buff) no hacen daño: son de estado.
PHYSICAL = frozenset({
    "tackle", "quick-attack", "vine-whip", "razor-leaf", "wing-attack", "body-slam", "poison-sting", "bulldoze",
    "bug-bite", "string-shot", "rock-throw", "rock-slide", "karate-chop", "lick", "metal-claw", "bite",
    "bonemerang", "psycho-cut", "spikes", "toxic-spikes", "meteor-mash", "substitute", "aerial-ace", "flame-wheel",
})

DAMAGE_CLASSES = ("physical", "special", "status")


def damage_class(move_id: str, kind: str) -> str:
    if kind == "buff":
        return "status"
    return "physical" if move_id in PHYSICAL else "special"


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
