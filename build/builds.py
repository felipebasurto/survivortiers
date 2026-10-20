"""Dos builds por Pokémon: la mejor cuerpo a cuerpo y la mejor a distancia.

Reglas (Felipe):
- Clase del atacante: físico si pa > sa, especial en otro caso (data/pokedex_export.json).
- Cuerpo a cuerpo: el grupo tiene al menos un ataque de tipo `melee` (data/game_stats.json, los 11 son físicos).
  A distancia: ningún ataque `melee`.
- Físico lleva Danza Espada (swords-dance); especial lleva Maquinación (nasty-plot). Los dos.
- Cada ataque es de la categoría de la clase (así el potenciador le sirve a todo el grupo). Un especial no tiene
  cuerpo a cuerpo: todos los `melee` son físicos.
- Sin relleno: Ataque Rápido, Placaje y Golpe Cuerpo no entran en ninguna build.
- Un grupo tiene dos o tres ataques y los huecos del vínculo del simulador (`picks.BOND_SLOTS`). Con dos ataques
  lleva el potenciador de ataque y Fortaleza o Agilidad; con tres, solo el de ataque.

El espacio de búsqueda es el mismo que la búsqueda de grupo (`simulator/results/fixed_group/`): las filas
que ya existen y cumplen las reglas se reutilizan, y solo se simula lo que falta, con las mismas semillas
(16 en la criba, 96 en el afinado, como `regen.py --sim`). La elección es la mediana del simulador.
"""
from __future__ import annotations

import csv
import itertools
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import passives
import picks

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# SURVIVOR_FIXED moves every run output (smoke tests); the published folder is the default.
FIXED = Path(os.environ["SURVIVOR_FIXED"]) if os.environ.get("SURVIVOR_FIXED") else ROOT / "simulator" / "results" / "fixed_group"
BUILDS_DIR = FIXED / "builds"
SCREEN_CSV = FIXED / "group_screen.csv"
REFINE_CSV = FIXED / "group_search.csv"
OUT_CSV = DATA / "builds.csv"

BUILDS = ("melee", "ranged")
FILLER = frozenset({"tackle", "quick-attack", "body-slam"})
CLASS_BUFF = {"physical": "swords-dance", "special": "nasty-plot"}
FOURTH = ("harden", "agility")
SCREEN_SEEDS = 16
REFINE_SEEDS = 96
REFINE_SEED0 = 1000
SEARCH_SECONDS = 900
REFINE_PER_SHAPE = picks.REFINE_PER_SHAPE
CSV_FIELDS = ["dex", "name", "build", "group", "median_s", "mean_s", "median_kills", "median_dealt",
              "median_score", "mean_score", "score_lo", "score_hi", "seeds"]


@lru_cache(maxsize=1)
def _pokedex() -> dict[int, dict]:
    return {int(p["dex"]): p for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}


@lru_cache(maxsize=1)
def _game_moves() -> dict[str, dict]:
    return json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))["moves"]


@lru_cache(maxsize=1)
def _sim_pools() -> dict[int, dict]:
    v3 = json.loads((ROOT / "simulator" / "v3" / "v3_data.json").read_text(encoding="utf8"))
    return {int(m["dex"]): m for m in v3["dex"]}


def attacker_class(dex: int) -> str:
    """physical si pa > sa; special en cualquier otro caso (también en empate, como pide la regla)."""
    p = _pokedex()[dex]
    return "physical" if float(p["pa"]) > float(p["sa"]) else "special"


def decent_attacks(dex: int) -> list[str]:
    """Ataques del pool del simulador (y el inicial) que lanzan daño, de la categoría de la clase y sin relleno."""
    cls = attacker_class(dex)
    moves = picks._v3_moves()
    game = _game_moves()
    mon = _sim_pools()[dex]
    out = []
    for mid in sorted(set(mon["pool"]) | {mon["start"]}):
        move = moves.get(mid)
        if move is None or move["kind"] == "buff":
            continue
        level = move["levels"][0]
        if (level.get("buff") or 0) != 0 or not float(level.get("dmg") or 0) > 0:
            continue
        if game[mid]["cat"] != cls or mid in FILLER:
            continue
        out.append(mid)
    return out


def _is_melee(mid: str) -> bool:
    return _game_moves()[mid]["kind"] == "melee"


def _group(attacks: list[str], buff: str, fourth: str | None) -> str:
    return "+".join([*attacks, buff, *([fourth] if fourth else [])])


def candidates(dex: int) -> dict[str, str]:
    """group name -> build (melee | ranged) for every group of this species that meets the rules."""
    cls = attacker_class(dex)
    buff = CLASS_BUFF[cls]
    atk = decent_attacks(dex)
    out: dict[str, str] = {}
    if len(atk) < 2:
        return out
    for a, b in itertools.permutations(atk, 2):
        for fourth in FOURTH:
            out[_group([a, b], buff, fourth)] = _kind([a, b])
    for trio in itertools.combinations(atk, 3):
        for lead in trio:
            comps = [x for x in trio if x != lead]
            out[_group([lead, *comps], buff, None)] = _kind(list(trio))
    return out


def _kind(attacks: list[str]) -> str:
    return "melee" if any(_is_melee(a) for a in attacks) else "ranged"


@lru_cache(maxsize=1)
def space() -> dict[int, dict[str, str]]:
    return {dex: c for dex in sorted(_pokedex()) if (c := candidates(dex))}


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _index(rows: list[dict]) -> dict[tuple[int, str], dict]:
    return {(int(r["dex"]), r["group"]): r for r in rows}


def missing_screen() -> list[tuple[int, str]]:
    have = _index(_rows(SCREEN_CSV))
    return [(dex, g) for dex, groups in space().items() for g in sorted(groups) if (dex, g) not in have]


def write_only(path: Path, keys: list[tuple[int, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{dex}|{g}\n" for dex, g in keys), encoding="utf8")
    return path


def screen_rows() -> dict[tuple[int, str], dict]:
    """Criba de 16 semillas: las filas de group_screen.csv del espacio, más las que se simularon para este build."""
    spaces = space()
    out = {k: r for k, r in _index(_rows(SCREEN_CSV)).items() if k[1] in spaces.get(k[0], {})}
    new = BUILDS_DIR / "screen_new.csv"
    if new.exists():
        out.update(_index(_rows(new)))
    return out


def shortlist(rows: dict[tuple[int, str], dict]) -> dict[tuple[int, str], list[dict]]:
    """Los dos mejores de cada forma (dos ataques o tres) y de cada build, por la criba."""
    spaces = space()
    pools: dict[tuple[int, str], dict[str, list[dict]]] = {}
    for (dex, group), row in rows.items():
        build = spaces[dex].get(group)
        if build is None:
            continue
        pools.setdefault((dex, build), {}).setdefault(picks.shape_of(group), []).append(row)
    out: dict[tuple[int, str], list[dict]] = {}
    for key, shapes in pools.items():
        picked: list[dict] = []
        for shape in sorted(shapes):
            picked.extend(sorted(shapes[shape], key=picks.group_order)[:REFINE_PER_SHAPE])
        out[key] = picked
    return out


def missing_refine(short: dict[tuple[int, str], list[dict]]) -> list[tuple[int, str]]:
    have = _index(_rows(REFINE_CSV))
    keys = {(dex, row["group"]) for (dex, _), rows in short.items() for row in rows}
    return sorted(k for k in keys if k not in have)


def finals() -> dict[tuple[int, str], dict]:
    """La elección: entre las filas de 96 semillas, la de mediana más alta en cada (especie, build)."""
    spaces = space()
    refined = _index(_rows(REFINE_CSV))
    new = BUILDS_DIR / "refine_new.csv"
    if new.exists():
        refined.update(_index(_rows(new)))
    best: dict[tuple[int, str], dict] = {}
    for (dex, group), row in refined.items():
        build = spaces.get(dex, {}).get(group)
        if build is None:
            continue
        cur = best.get((dex, build))
        if cur is None or picks.group_order(row) < picks.group_order(cur):
            best[(dex, build)] = row
    return best


def assemble() -> list[dict]:
    """Escribe data/builds.csv: una fila por (especie, build) elegida. Sin fila, esa build no existe."""
    chosen = finals()
    out = []
    names = {dex: p["name"] for dex, p in _pokedex().items()}
    for (dex, build), row in sorted(chosen.items()):
        out.append({"dex": dex, "name": names[dex], "build": build, "group": row["group"],
                    "median_s": row["median_s"], "mean_s": row["mean_s"], "median_kills": row["median_kills"],
                    "median_dealt": row["median_dealt"], "median_score": row["median_score"],
                    "mean_score": row["mean_score"], "score_lo": row["score_lo"], "score_hi": row["score_hi"],
                    "seeds": REFINE_SEEDS})
    return out


def read_rows(path: Path = OUT_CSV) -> list[dict]:
    """Las filas publicadas (data/builds.csv), ya comprobadas contra las reglas."""
    rows = _rows(path)
    errs = [e for r in rows for e in violations(int(r["dex"]), r["build"], r["group"])]
    if errs:
        raise ValueError("; ".join(errs[:5]))
    return rows


def write_csv(rows: list[dict], path: Path = OUT_CSV) -> None:
    with path.open("w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build_moves(group: str) -> tuple[list[str], int]:
    """Ids de la build en el orden del juego (ataques y luego potenciadores) y cuántos son potenciadores."""
    attacks, buff, fourth = picks.split_group(group)
    boosts = [b for b in (buff, fourth) if b]
    return attacks + boosts, len(boosts)


def violations(dex: int, build: str, group: str) -> list[str]:
    """Reglas de Felipe que una fila tiene que cumplir. Lista vacía si la fila es válida."""
    errs = []
    attacks, buff, fourth = picks.split_group(group)
    cls = attacker_class(dex)
    if buff != CLASS_BUFF[cls]:
        errs.append(f"{dex} {group}: el potenciador de clase es {buff}, no {CLASS_BUFF[cls]}")
    if any(a in FILLER for a in attacks):
        errs.append(f"{dex} {group}: lleva relleno normal")
    if any(_game_moves()[a]["cat"] != cls for a in attacks):
        errs.append(f"{dex} {group}: ataque de otra categoría que la clase {cls}")
    melee = any(_is_melee(a) for a in attacks)
    if build == "melee" and not melee:
        errs.append(f"{dex} {group}: build cuerpo a cuerpo sin ataque melee")
    if build == "ranged" and melee:
        errs.append(f"{dex} {group}: build a distancia con ataque melee")
    return errs


def public(rows: list[dict]) -> dict[str, dict]:
    """El JSON que lee la ficha (species.json, clave builds): dex -> {melee|ranged: {moves, nBoost, time, dealt,
    kills, score, cards}}. Las cartas son la prioridad de build/passives.py para ese grupo."""
    psim = passives.load()
    out: dict[str, dict] = {}
    for r in rows:
        dex = int(r["dex"])
        moves, n_boost = build_moves(r["group"])
        out.setdefault(str(dex), {})[r["build"]] = {
            "moves": moves, "nBoost": n_boost,
            "time": round(float(r["median_s"]), 1), "dealt": round(float(r["median_dealt"])),
            "kills": round(float(r["median_kills"]), 1), "score": round(float(r["median_score"]), 2),
            "cards": passives.priority(dex, moves, psim)}
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rows = assemble()
    errs = [e for r in rows for e in violations(int(r["dex"]), r["build"], r["group"])]
    if errs:
        for e in errs[:40]:
            print("ERROR " + e, file=sys.stderr)
        return 1
    if "--check" in argv:
        print(f"builds: {len(rows)} filas válidas")
    else:
        write_csv(rows)
        print(f"builds: {len(rows)} filas → {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
