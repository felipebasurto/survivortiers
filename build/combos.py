"""Combo de cobertura por Pokémon: hasta tres ataques y un potenciador, que en el juego se lanzan juntos en un vínculo.

Qué mide, sobre los 966 Pokémon por igual:
  super    % de rivales a los que los ataques pegan super efectivo (×1,6 o más, con la tabla de tipos del juego)
  neutral  % de rivales a los que los ataques nunca pegan resistido (el mejor ataque es ×1 o más)

En el juego no hay bonificación por tipo propio (STAB): el daño es daño del ataque × ataque del jugador × multiplicador
de tipo contra el rival × clima, y los ataques normales nunca son super efectivos.

Qué elige, de los ataques que ofrece el juego a ese Pokémon (POOL.normal + POOL de sus tipos):
  1. Hueco 1: el mejor ataque de la simulación (`best_move` de data/ranking_definitive.csv), siempre.
  2. Huecos 2 y 3: el ataque que más cobertura añade (rivales nuevos en super efectivo y en no resistido). Si varios
     empatan, el de más daño total, que cuenta todos los proyectiles de los ataques de varios disparos o de área.
     Cuando ya no queda cobertura por ganar, rellena con el de más daño que no sea normal (los normales solo entran
     si abren al menos un 2 % de rivales, salvo que el Pokémon no tenga otra cosa que ofrecer).
  3. Potenciador: el de mejor score_rel.

Datos: data/move_pool.json, data/move_mechanics.json, data/type_matrix.json (los exporta
build/export_move_mechanics.js desde el juego) y data/move_tierlist_v4.csv.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

SUPER = 1.05     # como G.Types.label(): por encima es super efectivo
NEUTRAL = 0.95   # por debajo es resistido


def _load():
    pool = json.loads((DATA / "move_pool.json").read_text(encoding="utf8"))
    mech = json.loads((DATA / "move_mechanics.json").read_text(encoding="utf8"))
    matrix = json.loads((DATA / "type_matrix.json").read_text(encoding="utf8"))
    rows = {}
    with open(DATA / "move_tierlist_v4.csv", encoding="utf8") as f:
        for r in csv.DictReader(f):
            rows[r["move_id"]] = r
    return pool, mech, matrix, rows


def _mult(matrix: dict, atk: str, defender: list[str]) -> float:
    return matrix[atk][",".join(sorted(defender))]


ATTACK_SLOTS = 3
# Un ataque normal solo suma neutral, así que solo cuenta como «mejora la cobertura» si abre al menos este % de rivales.
NORMAL_MIN_GAIN = 0.02


def total_damage(row: dict, mech: dict) -> float:
    """Daño de un ataque contando todos sus proyectiles: dps_m15 (de un solo proyectil) × disparos por lanzamiento.
    «count» de move_mechanics.json son los proyectiles de ráfagas, abanicos, órbitas, bumeranes, meteoros y minas, y los
    saltos de las cadenas; los ataques de un solo golpe, rayo o aura cuentan 1."""
    return float(row["dps_m15"] or 0) * max(1, mech["count"])


def _coverage(matrix: dict, types: list[str], enemies: list[list[str]], cache: dict) -> tuple[int, int]:
    """(rivales a los que algún ataque pega super efectivo, rivales a los que ninguno resiste). Solo depende del
    conjunto de tipos de ataque, así que se guarda en `cache`."""
    key = frozenset(types)
    if key not in cache:
        super_hits = neutral_hits = 0
        for enemy in enemies:
            best = max(_mult(matrix, t, enemy) for t in key)
            super_hits += best > SUPER
            neutral_hits += best >= NEUTRAL
        cache[key] = (super_hits, neutral_hits)
    return cache[key]


def pick_attacks(candidates: list[str], best_move: str, rows: dict, mech: dict, matrix: dict,
                 enemies: list[list[str]], cache: dict) -> list[str]:
    damage = {i: total_damage(rows[i], mech[i]) for i in candidates}
    chosen = [best_move]
    while len(chosen) < ATTACK_SLOTS:
        have = [rows[i]["type"] for i in chosen]
        base = _coverage(matrix, have, enemies, cache)
        scored = []
        for i in candidates:
            if i in chosen:
                continue
            s, n = _coverage(matrix, have + [rows[i]["type"]], enemies, cache)
            gain = (s - base[0]) + (n - base[1])
            if rows[i]["type"] == "normal" and gain < NORMAL_MIN_GAIN * len(enemies):
                gain = 0
            scored.append((gain, i))
        useful = [(g, i) for g, i in scored if g > 0]
        if useful:
            top = max(g for g, _ in useful)
            pick = max((i for g, i in useful if g == top), key=lambda i: damage[i])
        else:
            non_normal = [i for _, i in scored if rows[i]["type"] != "normal"]
            rest = non_normal or [i for _, i in scored]
            if not rest:
                break
            pick = max(rest, key=lambda i: damage[i])
        chosen.append(pick)
    return chosen


def compute_all(types_by_dex: dict[int, list[str]], best_move_by_dex: dict[int, str]) -> dict[int, dict]:
    """Devuelve {dex: {"moves": [ids de los ataques + potenciador], "types", "super": %, "neutral": %}}."""
    pool, mech, matrix, rows = _load()
    boost = lambda mid: float(rows[mid]["score_rel"] or 0)
    everyone = list(types_by_dex.values())
    out: dict[int, dict] = {}
    cache: dict = {}
    for dex, types in types_by_dex.items():
        ids = set(pool["normal"])
        for t in types:
            ids.update(pool.get(t, []))
        attacks = sorted(i for i in ids if mech[i]["kind"] != "buff")
        buffs = sorted(i for i in ids if mech[i]["kind"] == "buff")
        best = best_move_by_dex[dex]
        if best not in attacks:
            raise ValueError(f"el mejor ataque de la simulación ({best}) no está entre los que aprende {dex}")
        trio = pick_attacks(attacks, best, rows, mech, matrix, everyone, cache)
        group = trio + ([max(buffs, key=boost)] if buffs else [])
        super_hits, neutral_hits = _coverage(matrix, [rows[i]["type"] for i in trio], everyone, cache)
        n = len(everyone)
        # types: tipos de ataque distintos (3 como máximo). Con menos de tres, el combo cubre menos rivales.
        out[dex] = {"moves": group, "types": len({rows[i]["type"] for i in trio}),
                    "super": round(100 * super_hits / n), "neutral": round(100 * neutral_hits / n)}
    return out


if __name__ == "__main__":
    import sys

    dex = {p["dex"]: p["types"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    with open(DATA / "ranking_definitive.csv", encoding="utf8") as f:
        best_by_dex = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
    res = compute_all(dex, best_by_dex)
    for d in map(int, sys.argv[1:]):
        r = res[d]
        print(d, r["super"], r["neutral"], r["moves"])
