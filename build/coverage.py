"""Cobertura de tipos de una build contra los Pokémon que salen como enemigos.

Cuenta especies enemigas, cada una una vez (simulator/v3/v3_data.json `tiers`: el juego saca 7 al azar de cada tramo
en cada partida), y mira la tabla de tipos del juego (`tmult`, la que aplica el simulador a cada golpe):
- le pega bien: algún ataque de la build es superefectivo (más de ×1);
- la resiste: todos los ataques de la build le hacen menos de ×1.
El bonus de ×1,2 de un Pokémon de un solo tipo con sus ataques de su tipo (player.js monoType) no es de la tabla y no
cambia estas cuentas; la ficha lo dice aparte.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "simulator" / "v3" / "v3_data.json"
TYPES = ("normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic",
         "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy")


@lru_cache(maxsize=1)
def _v3() -> dict:
    return json.loads(V3.read_text(encoding="utf8"))


def chart(atk: str, combo: str) -> float:
    return _v3()["tmult"][atk][combo]


@lru_cache(maxsize=1)
def enemies() -> dict[int, list[str]]:
    """dex -> tipos de cada especie que sale como enemigo, en cualquier tramo."""
    out: dict[int, list[str]] = {}
    for tier in _v3()["tiers"]:
        for c in tier["cands"]:
            out.setdefault(int(c["dex"]), list(c["types"]))
    return out


@lru_cache(maxsize=1)
def tiers() -> list[tuple[int, dict[int, list[str]]]]:
    """(segundo en que empieza, dex -> tipos) de cada tramo."""
    return [(int(t["from"]), {int(c["dex"]): list(c["types"]) for c in t["cands"]}) for t in _v3()["tiers"]]


def move_type(mid: str) -> str:
    return _v3()["moves"][mid]["type"]


def attack_types(moves: list[str]) -> list[str]:
    v3 = _v3()["moves"]
    return sorted({v3[m]["type"] for m in moves if v3[m]["kind"] != "buff"})


def best_mult(types: list[str], foe: list[str]) -> float:
    combo = "/".join(foe)
    return max(chart(t, combo) for t in types)


def of_types(types: list[str], pool: dict[int, list[str]] | None = None) -> dict:
    """good: especies a las que algún tipo pega bien; resist: especies que resisten todos; resist_by: tipo enemigo ->
    cuántas de las que resisten lo tienen."""
    pool = enemies() if pool is None else pool
    good = resist = 0
    by: Counter[str] = Counter()
    for foe in pool.values():
        m = best_mult(types, foe)
        good += m > 1
        if m < 1:
            resist += 1
            by.update(foe)
    return {"n": len(pool), "good": good, "resist": resist, "resist_by": dict(by.most_common())}


def of_build(moves: list[str]) -> dict:
    return of_types(attack_types(moves))
