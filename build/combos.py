"""Trío de ataques con más cobertura por Pokémon (el «combo» que propone el vídeo: tres ataques de tipos distintos
más un potenciador, que en el juego se lanzan juntos en un vínculo).

Qué mide, sobre los 966 Pokémon por igual:
  super    % de rivales a los que el trío pega super efectivo (×1,6 o más, con la tabla de tipos del juego)
  neutral  % de rivales a los que el trío nunca pega resistido (el mejor ataque es ×1 o más)

Qué elige: de los ataques que ofrece el juego a ese Pokémon (POOL.normal + POOL de sus tipos), el más fuerte
de cada tipo de ataque (dps_m15 de data/move_tierlist_v4.csv), y de los potenciadores el de mejor score_rel.

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


def compute_all(types_by_dex: dict[int, list[str]]) -> dict[int, dict]:
    """Devuelve {dex: {"moves": [ids del trío + potenciador], "super": %, "neutral": %}}."""
    pool, mech, matrix, rows = _load()
    dps = lambda mid: float(rows[mid]["dps_m15"] or 0)
    boost = lambda mid: float(rows[mid]["score_rel"] or 0)
    everyone = list(types_by_dex.values())
    out: dict[int, dict] = {}
    for dex, types in types_by_dex.items():
        ids = set(pool["normal"])
        for t in types:
            ids.update(pool.get(t, []))
        attacks = [i for i in ids if mech[i]["kind"] != "buff"]
        buffs = [i for i in ids if mech[i]["kind"] == "buff"]
        best_per_type: dict[str, str] = {}
        for i in attacks:
            t = rows[i]["type"]
            if t not in best_per_type or dps(i) > dps(best_per_type[t]):
                best_per_type[t] = i
        trio = sorted(best_per_type.values(), key=lambda i: -dps(i))[:3]
        group = trio + ([max(buffs, key=boost)] if buffs else [])

        super_hits = neutral_hits = 0
        for enemy in everyone:
            best = max(_mult(matrix, rows[i]["type"], enemy) for i in trio)
            super_hits += best > SUPER
            neutral_hits += best >= NEUTRAL
        n = len(everyone)
        # types: tipos de ataque distintos del trío (3 como máximo). Con menos, el trío no cubre tres tipos.
        out[dex] = {"moves": group, "types": len(trio), "super": round(100 * super_hits / n),
                    "neutral": round(100 * neutral_hits / n)}
    return out


if __name__ == "__main__":
    import sys

    dex = {p["dex"]: p["types"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    res = compute_all(dex)
    for d in map(int, sys.argv[1:]):
        r = res[d]
        print(d, r["super"], r["neutral"], [rows_name for rows_name in r["moves"]])
