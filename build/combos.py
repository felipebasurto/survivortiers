"""Combo de cobertura por Pokémon: dos ataques y dos potenciadores, que en el juego se lanzan juntos en un vínculo.

Qué mide, sobre los 966 Pokémon por igual:
  super    % de rivales a los que los ataques pegan super efectivo (×1,6 o más, con la tabla de tipos del juego)
  neutral  % de rivales a los que los ataques nunca pegan resistido (el mejor ataque es ×1 o más)

En el juego no hay bonificación por tipo propio (STAB): el daño es daño del ataque × ataque del jugador × multiplicador
de tipo contra el rival × clima, y los ataques normales nunca son super efectivos.

Qué elige, de los ataques que ofrece el juego a ese Pokémon (POOL.normal + POOL de sus tipos):
  1. Si la búsqueda de grupo fijo tiene una fila para esa especie
     (`simulator/results/fixed_group/group_search.csv`), los ataques del grupo con mejor mediana
     (si empatan, mejor media, bajas y daño). Ahí entran Hex con quemadura, veneno o ralentización, las
     parejas y tríos de los mejores ataques (de cualquier categoría) y las parejas de dos dashes,
     cada uno con cada relleno de potenciadores (Danza Espada, Danza Dragón o Maquinación; Fortaleza
     o Agilidad), y gana el que más puntúa en la simulación (aguantar, daño y bajas). Los
     potenciadores publicados son los del grupo ganador. La elección sale de build/picks.py, la
     misma que usa el ranking. La ficha no publica este grupo tal cual: `follow_builds` lo cambia por la build que
     enseña (build/builds.py), y de ahí salen los ataques, los potenciadores y la cobertura que se ven.
  2. Si no hay búsqueda, hueco 1 es el mejor ataque de la simulación (`best_move`). Si ese ataque
     tiene un compañero de sinergia (Hex con estado, o dos dashes), el hueco 2 es ese compañero
     a distancia cuando hay uno; si no, el de más cobertura.
  3. El resto de huecos: el ataque que más cobertura añade (rivales nuevos en super efectivo y en no resistido). Si
     varios empatan, el de más daño total, que cuenta todos los proyectiles de los ataques de varios disparos o de
     área. Cuando ya no queda cobertura por ganar, rellena con el de más daño que no sea normal (los normales solo
     entran si abren al menos un 2 % de rivales, salvo que el Pokémon no tenga otra cosa que ofrecer).
     Mientras quede un ataque a distancia, no se rellena con cuerpo a cuerpo.
  4. Opcionales: se sigue con la cobertura tres ataques más (ALT_SLOTS), para los huecos que se abren más tarde.
  5. Potenciadores: los del grupo ganador. Sin búsqueda, el que sube la categoría del primer ataque
     (Maquinación sube el especial; Danza Espada y Danza Dragón, el físico) y Fortaleza.

Datos: data/move_pool.json, data/move_mechanics.json, data/type_matrix.json (los exporta
build/export_move_mechanics.js desde el juego) y data/move_tierlist_v4.csv.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import picks

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


ATTACK_SLOTS = 2
ALT_SLOTS = 3
FALLBACK_DEF = "harden"
# Un ataque normal solo suma neutral, así que solo cuenta como «mejora la cobertura» si abre al menos este % de rivales.
NORMAL_MIN_GAIN = 0.02


def total_damage(row: dict, mech: dict) -> float:
    """Daño de un ataque contando todos sus proyectiles: dps (daño por segundo de la simulación, de un solo proyectil) × disparos por lanzamiento.
    «count» de move_mechanics.json son los proyectiles de ráfagas, abanicos, órbitas, bumeranes, meteoros y minas, y los
    saltos de las cadenas; los ataques de un solo golpe, rayo o aura cuentan 1."""
    return float(row["dps"] or 0) * max(1, mech["count"])


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


# Written by `pokesim synergy` and refined by build/regen.py (fresh seeds, then the contenders on many).
SEARCH_CSV = DATA.parent / "simulator" / "results" / "fixed_group" / "group_search.csv"


def _synergy_flags() -> dict[str, tuple[bool, bool, bool]]:
    """move id -> (hex > 1, applies burn/poison/slow, dash). Level 1 of v3, same fields the sim pairs on."""
    out = {}
    for mid, move in picks._v3_moves().items():
        level = move["levels"][0]
        status = any(float(level.get(k) or 0) > 0 for k in ("burn", "poison", "slow"))
        out[mid] = (float(level.get("hex") or 0) > 1, status, move["kind"] == "dash")
    return out


def _pairs(a: str, b: str, flags: dict[str, tuple[bool, bool, bool]]) -> bool:
    if a not in flags or b not in flags:
        return False
    ha, sa, da = flags[a]
    hb, sb, db = flags[b]
    return (ha and sb) or (hb and sa) or (da and db)


def _special_species() -> dict[int, bool]:
    raw = json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))
    return {int(p["dex"]): float(p["sa"]) > float(p["pa"]) for p in raw}


def _attack_buff(attacks: list[str], cats: dict[str, str], special: bool, available: list[str]) -> str | None:
    """For a species the search did not score: the buff that raises the first categorised attack
    (`sa > pa` when none is), from the game's buff stats. Danza Espada before Danza Dragón."""
    lead = next((cats[a] for a in attacks if cats.get(a) in ("physical", "special")), "special" if special else "physical")
    side = picks.attack_buff_side()
    return next((b for b in sorted(available) if side.get(b) == lead and b != "dragon-dance"),
                next((b for b in available if side.get(b) == lead), None))


def _search_picks() -> dict[int, tuple[list[str], list[str]]]:
    """dex -> (attack ids, buff ids) of the winning searched group (build/picks.best_groups)."""
    if not SEARCH_CSV.exists():
        return {}
    out = {}
    for dex, row in picks.best_groups(picks.load_rows(SEARCH_CSV)).items():
        attacks, buff, fourth = picks.split_group(row["group"])
        out[dex] = (attacks, [b for b in (buff, fourth) if b])
    return out


def pick_attacks(candidates: list[str], best_move: str, rows: dict, mech: dict, matrix: dict,
                 enemies: list[list[str]], cache: dict, slots: int = ATTACK_SLOTS,
                 preset: list[str] | None = None, flags: dict | None = None) -> list[str]:
    damage = {i: total_damage(rows[i], mech[i]) for i in candidates}
    chosen = [m for m in (preset or [best_move]) if m in damage or m == best_move]
    if not chosen:
        chosen = [best_move]
    while len(chosen) < slots:
        # Without a searched group, the second attack stays the synergy partner when the pool has one.
        if preset is None and len(chosen) == 1 and flags:
            syn = [i for i in candidates if i not in chosen and _pairs(best_move, i, flags)]
            ranged_syn = [i for i in syn if rows[i].get("kind") != "melee"]
            if ranged_syn:
                syn = ranged_syn
            if syn:
                chosen.append(max(syn, key=lambda i: damage[i]))
                continue
        have = [rows[i]["type"] for i in chosen]
        base = _coverage(matrix, have, enemies, cache)
        scored = []
        ranged_open = any(rows[i].get("kind") != "melee" and i not in chosen for i in candidates)
        for i in candidates:
            if i in chosen:
                continue
            if rows[i].get("kind") == "melee" and ranged_open and len(chosen) >= 1:
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
    """Devuelve {dex: {"moves": [ids de los ataques + potenciador], "alts": [ids opcionales], "types", "super": %,
    "neutral": %}}."""
    pool, mech, matrix, rows = _load()
    searched = _search_picks()
    flags = _synergy_flags()
    cats = picks.categories()
    special = _special_species()
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
        if best not in attacks and best in rows:
            # el ataque inicial propio de la especie (p. ej. Confusión de Psyduck) no está en POOL, pero lo lleva desde el inicio
            attacks.append(best)
        preset, searched_buffs = searched.get(dex, ([], []))
        preset = [m for m in preset if m in rows]
        for move in preset:
            if move not in attacks:
                attacks.append(move)
        if best not in attacks:
            raise ValueError(f"el mejor ataque de la simulación ({best}) no está entre los que aprende {dex}")
        # The search names every attack it bonded. Later slots stay coverage.
        # A species the search did not score keeps the synergy partner, as before.
        found = len(preset) >= 2
        n_atk = len(preset) if found else ATTACK_SLOTS
        ranked = pick_attacks(attacks, best, rows, mech, matrix, everyone, cache, n_atk + ALT_SLOTS,
                              preset if found else None, None if found else flags)
        trio, alts = ranked[:n_atk], ranked[n_atk:]
        want = searched_buffs if found else [_attack_buff(trio, cats, special.get(dex, False), buffs), FALLBACK_DEF]
        boosts = [b for b in want if b in buffs]
        group = trio + boosts
        super_hits, neutral_hits = _coverage(matrix, [rows[i]["type"] for i in trio], everyone, cache)
        n = len(everyone)
        # types: tipos de ataque distintos (3 como máximo). Con menos de tres, el combo cubre menos rivales.
        out[dex] = {"moves": group, "nBoost": len(boosts), "alts": alts, "types": len({rows[i]["type"] for i in trio}),
                    "super": round(100 * super_hits / n), "neutral": round(100 * neutral_hits / n)}
    return out


def follow_builds(combo: dict[int, dict], lead: dict[int, dict], types_by_dex: dict[int, list[str]]) -> dict[int, dict]:
    """El grupo y la cobertura de cada especie, tomados de la build que enseña la ficha (build/builds.py lead_builds) en
    vez de la del grupo buscado. Las especies sin build conservan el grupo de compute_all."""
    _, mech, matrix, rows = _load()
    everyone = list(types_by_dex.values())
    cache: dict = {}
    out = dict(combo)
    for dex, b in lead.items():
        group = list(b["moves"])
        attacks = [m for m in group if mech[m]["kind"] != "buff"]
        if not attacks:
            continue
        types = [rows[m]["type"] for m in attacks]
        super_hits, neutral_hits = _coverage(matrix, types, everyone, cache)
        out[dex] = {**combo[dex], "moves": group, "nBoost": len(group) - len(attacks),
                    "alts": [m for m in combo[dex]["alts"] if m not in group], "types": len(set(types)),
                    "super": round(100 * super_hits / len(everyone)), "neutral": round(100 * neutral_hits / len(everyone))}
    return out


if __name__ == "__main__":
    import sys

    dex = {p["dex"]: p["types"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    with open(DATA / "ranking_definitive.csv", encoding="utf8") as f:
        best_by_dex = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
    res = compute_all(dex, best_by_dex)
    for d in map(int, sys.argv[1:]):
        r = res[d]
        print(d, r["super"], r["neutral"], r["moves"], "opcionales:", r["alts"])
