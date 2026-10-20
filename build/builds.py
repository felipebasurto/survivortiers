"""Las builds de cada Pokémon, elegidas solo con filas que el simulador ya produjo: dos ofensivas (la mejor cuerpo a
cuerpo y la mejor a distancia), una defensiva opcional con Fortaleza, y el ataque con el que conviene empezar.

Ninguna regla es a mano: cada elección sale de una columna de la simulación.

- Empezar: el mejor ataque de daño de la especie en `solo_screen_out/rank_best_starter.csv` (`best_start`), de cualquier
  categoría y de cualquier rango. Nunca un potenciador ni Sustituto.
- Ofensiva: tres ataques y el potenciador de ataque que sube su categoría (Danza Espada si son físicos, Maquinación si
  son especiales), sin Fortaleza ni Agilidad. Cuerpo a cuerpo si algún ataque es `melee` (los 11 son físicos); a
  distancia si no. Gana la fila de mayor `median_score`; entre las que el azar de las semillas no separa de ella
  (su mediana cae dentro del intervalo `boot_lo`/`score_lo` de la ganadora) se prefiere la que lidera con el ataque
  inicial. Es la elección de `picks.group_order` con ese único desempate.
- Defensiva: el mejor grupo ya simulado que lleva Fortaleza (`harden`), con la misma preferencia por el ataque inicial.
  Si la especie no tiene ninguno, no se inventa.
- Relleno normal: un ataque de tipo normal que la tabla de ataques del simulador (`data/move_tierlist_v4.csv`) no
  pone en el tier S ni en el A solo entra si la especie es de tipo normal. Sustituto no es un ataque y nunca entra.

Filas que se leen, de más a menos semillas: `group_search.csv` y `builds/refine_new.csv` (96 semillas, seed0 1000);
`group_screen.csv` y `builds/screen_new.csv` (16 semillas). Las de 16 solo se usan para una build ofensiva a la que no
llega ninguna fila de 96. Nada se simula aquí.
"""
from __future__ import annotations

import csv
import itertools
import json
import sys
from functools import lru_cache
from pathlib import Path

import passives
import picks

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIXED = ROOT / "simulator" / "results" / "fixed_group"
BUILDS_DIR = FIXED / "builds"
SCREEN_CSV = FIXED / "group_screen.csv"
REFINE_CSV = FIXED / "group_search.csv"
STARTER_CSV = FIXED / "solo_screen_out" / "rank_best_starter.csv"
TIERLIST_CSV = DATA / "move_tierlist_v4.csv"
OUT_CSV = DATA / "builds.csv"

BUILDS = ("melee", "ranged")
DEFENSIVE = "defensive"
KINDS = (*BUILDS, DEFENSIVE)
ATTACK_BUFF = {"physical": "swords-dance", "special": "nasty-plot"}
DEFENSE_MOVE = "harden"
NOT_AN_ATTACK = "substitute"
KEEP_TIERS = frozenset({"S", "A"})
SCREEN_SEEDS = 16
REFINE_SEEDS = 96
REFINE_SEED0 = 1000
SEARCH_SECONDS = 900
REFINE_PER_SHAPE = 2
SOURCES_96 = (("group_search", REFINE_CSV), ("refine_new", BUILDS_DIR / "refine_new.csv"))
SOURCES_16 = (("group_screen", SCREEN_CSV), ("screen_new", BUILDS_DIR / "screen_new.csv"))
SEEDS = {"group_search": REFINE_SEEDS, "refine_new": REFINE_SEEDS, "group_screen": SCREEN_SEEDS,
         "screen_new": SCREEN_SEEDS}
CSV_FIELDS = ["dex", "name", "build", "group", "median_s", "mean_s", "median_kills", "median_dealt",
              "median_score", "mean_score", "score_lo", "score_hi", "seeds", "source"]


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


@lru_cache(maxsize=1)
def _tiers() -> dict[str, str]:
    with TIERLIST_CSV.open(encoding="utf8", newline="") as f:
        return {r["move_id"]: r["tier"] for r in csv.DictReader(f)}


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def is_filler(dex: int, mid: str) -> bool:
    """Sustituto, o un ataque normal fuera de los tiers S y A para una especie que no es de tipo normal."""
    if mid == NOT_AN_ATTACK:
        return True
    if _game_moves()[mid]["type"] != "normal" or "normal" in _pokedex()[dex]["types"]:
        return False
    return _tiers().get(mid) not in KEEP_TIERS


def category(mid: str) -> str:
    return _game_moves()[mid]["cat"]


def _is_melee(mid: str) -> bool:
    return _game_moves()[mid]["kind"] == "melee"


def kind_of(attacks: list[str]) -> str:
    return "melee" if any(_is_melee(a) for a in attacks) else "ranged"


def offensive_category(attacks: list[str]) -> str | None:
    """La categoría común de los ataques, o None si mezclan físico y especial."""
    cats = {category(a) for a in attacks}
    return cats.pop() if len(cats) == 1 else None


@lru_cache(maxsize=1)
def starts() -> dict[int, str]:
    """dex -> `best_start` de rank_best_starter.csv: el ataque de daño con el que mejor empieza la especie."""
    moves = picks._v3_moves()
    out = {}
    for r in _rows(STARTER_CSV):
        dex, mid = int(r["dex"]), r["best_start"]
        move = moves.get(mid)
        if move is None or move["kind"] == "buff" or mid == NOT_AN_ATTACK or not float(move["levels"][0].get("dmg") or 0) > 0:
            raise ValueError(f"{dex}: el mejor inicial {mid} no es un ataque de daño")
        out[dex] = mid
    return out


def default_starts() -> dict[int, str]:
    """dex -> el ataque con el que el juego deja empezar a la especie (no entra en ninguna elección)."""
    return {dex: p["start_move_id"] for dex, p in _pokedex().items()}


@lru_cache(maxsize=2)
def _pool(sources: tuple) -> dict[int, list[dict]]:
    """dex -> filas de esas fuentes, cada una con su `source` y sus `seeds`. Una clave (dex, grupo) cuenta una vez."""
    seen: set[tuple[int, str]] = set()
    out: dict[int, list[dict]] = {}
    for name, path in sources:
        if not path.exists():
            continue
        for r in _rows(path):
            key = (int(r["dex"]), r["group"])
            if key in seen:
                continue
            seen.add(key)
            out.setdefault(key[0], []).append({**r, "source": name, "seeds": SEEDS[name]})
    return out


def _lead(row: dict) -> str:
    return picks.split_group(row["group"])[0][0]


def within_noise(best: dict, row: dict) -> bool:
    """El azar de las semillas no separa `row` de `best`: su mediana de aguante y su puntuación caen dentro de los
    intervalos de bootstrap de la ganadora (`boot_lo` y `score_lo`)."""
    return float(row["median_s"]) >= float(best["boot_lo"]) and picks.score(row) >= float(best["score_lo"])


def choose(rows: list[dict], start: str) -> dict:
    """La mejor fila por `picks.group_order`; si alguna que el azar no separa de ella lidera con `start`, la mejor así."""
    ranked = sorted(rows, key=picks.group_order)
    best = ranked[0]
    for row in ranked:
        if _lead(row) == start and within_noise(best, row):
            return row
    return best


def offensive_ok(dex: int, group: str) -> str | None:
    """El tipo de build (melee | ranged) si el grupo es ofensivo según las reglas; None si no."""
    attacks, buff, fourth = picks.split_group(group)
    if len(attacks) != 3 or fourth or buff is None or len(set(attacks)) != 3:
        return None
    cat = offensive_category(attacks)
    if cat is None or buff != ATTACK_BUFF[cat] or any(is_filler(dex, a) for a in attacks):
        return None
    return kind_of(attacks)


def defensive_ok(dex: int, group: str) -> bool:
    attacks, _, fourth = picks.split_group(group)
    return fourth == DEFENSE_MOVE and len(attacks) >= 2 and not any(is_filler(dex, a) for a in attacks)


def finals() -> dict[tuple[int, str], dict]:
    """La elección: {(dex, melee | ranged | defensive): fila}. La ofensiva sale de las filas de 96 semillas y solo
    cae a las de 16 cuando esa build no tiene ninguna. La defensiva, solo de las de 96."""
    p96, p16 = _pool(SOURCES_96), _pool(SOURCES_16)
    best_start = starts()
    out: dict[tuple[int, str], dict] = {}
    for dex in sorted(_pokedex()):
        for pool in (p96, p16):
            by_kind: dict[str, list[dict]] = {}
            for row in pool.get(dex, []):
                kind = offensive_ok(dex, row["group"])
                if kind:
                    by_kind.setdefault(kind, []).append(row)
            for kind, rows in by_kind.items():
                out.setdefault((dex, kind), choose(rows, best_start[dex]))
        defense = [r for r in p96.get(dex, []) if defensive_ok(dex, r["group"])]
        if defense:
            out[(dex, DEFENSIVE)] = choose(defense, best_start[dex])
    return out


def assemble() -> list[dict]:
    """Escribe data/builds.csv: una fila por (especie, build) elegida. Sin fila, esa build no existe."""
    names = {dex: p["name"] for dex, p in _pokedex().items()}
    out = []
    for (dex, build), row in sorted(finals().items()):
        out.append({"dex": dex, "name": names[dex], "build": build, "group": row["group"],
                    "median_s": row["median_s"], "mean_s": row["mean_s"], "median_kills": row["median_kills"],
                    "median_dealt": row["median_dealt"], "median_score": row["median_score"],
                    "mean_score": row["mean_score"], "score_lo": row["score_lo"], "score_hi": row["score_hi"],
                    "seeds": row["seeds"], "source": row["source"]})
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
    """Reglas que una fila publicada tiene que cumplir. Lista vacía si la fila es válida."""
    if build == DEFENSIVE:
        return [] if defensive_ok(dex, group) else [f"{dex} {group}: no es una build defensiva válida"]
    if build not in BUILDS:
        return [f"{dex} {group}: build desconocida {build}"]
    kind = offensive_ok(dex, group)
    if kind is None:
        return [f"{dex} {group}: no es una build ofensiva válida (tres ataques de una categoría, su potenciador, "
                "sin Fortaleza ni Agilidad ni relleno)"]
    if kind != build:
        return [f"{dex} {group}: es una build {kind}, no {build}"]
    return []


def public(rows: list[dict]) -> dict[str, dict]:
    """El JSON que lee la ficha (species.json, clave builds): dex -> {melee|ranged: {moves, nBoost, time, dealt,
    kills, score, cards}}. Las cartas son la prioridad de build/passives.py para ese grupo."""
    psim = passives.load()
    out: dict[str, dict] = {}
    for r in rows:
        if r["build"] not in BUILDS:
            continue
        dex = int(r["dex"])
        moves, n_boost = build_moves(r["group"])
        out.setdefault(str(dex), {})[r["build"]] = {
            "moves": moves, "nBoost": n_boost,
            "time": round(float(r["median_s"]), 1), "dealt": round(float(r["median_dealt"])),
            "kills": round(float(r["median_kills"]), 1), "score": round(float(r["median_score"]), 2),
            "cards": passives.priority(dex, moves, psim)}
    return out


def public_defensive(rows: list[dict]) -> dict[str, dict]:
    """species.json, clave defensive: dex -> la misma forma que una build ofensiva. Solo las especies que tienen una."""
    psim = passives.load()
    out: dict[str, dict] = {}
    for r in rows:
        if r["build"] != DEFENSIVE:
            continue
        dex = int(r["dex"])
        moves, n_boost = build_moves(r["group"])
        out[str(dex)] = {
            "moves": moves, "nBoost": n_boost,
            "time": round(float(r["median_s"]), 1), "dealt": round(float(r["median_dealt"])),
            "kills": round(float(r["median_kills"]), 1), "score": round(float(r["median_score"]), 2),
            "cards": passives.priority(dex, moves, psim)}
    return out


def lead_builds(rows: list[dict]) -> dict[int, dict]:
    """dex -> la build que encabeza la ficha: la ofensiva de mayor puntuación (la cuerpo a cuerpo si empatan) o, sin
    ninguna ofensiva, la defensiva. Es la misma elección que build/static_ficha.py lead_build."""
    offensive, defensive = public(rows), public_defensive(rows)
    out = {}
    for dex in sorted(set(offensive) | set(defensive), key=int):
        pair = offensive.get(dex)
        if not pair:
            out[int(dex)] = defensive[dex]
        elif len(pair) == 1:
            out[int(dex)] = next(iter(pair.values()))
        else:
            out[int(dex)] = pair["ranged"] if pair["ranged"]["score"] > pair["melee"]["score"] else pair["melee"]
    return out


def seed_counts() -> dict[str, int]:
    """Cuántas builds ofensivas publicadas salen de filas de 16 semillas (`n16`) y cuántas hay (`n`)."""
    offensive = [r for r in read_rows() if r["build"] in BUILDS]
    return {"n16": sum(int(r["seeds"]) == SCREEN_SEEDS for r in offensive), "n": len(offensive)}


def public_starts() -> dict[str, str]:
    """species.json, clave starts: dex -> ataque con el que empezar."""
    return {str(dex): mid for dex, mid in sorted(starts().items())}


# --------------------------------------------------------------------- espacio de búsqueda para una corrida nueva

def decent_attacks(dex: int, cat: str) -> list[str]:
    """Ataques del pool del simulador (y el inicial) que lanzan daño, de esa categoría y sin relleno."""
    moves = picks._v3_moves()
    mon = _sim_pools()[dex]
    out = []
    for mid in sorted(set(mon["pool"]) | {mon["start"]}):
        move = moves.get(mid)
        if move is None or move["kind"] == "buff" or is_filler(dex, mid):
            continue
        level = move["levels"][0]
        if (level.get("buff") or 0) != 0 or not float(level.get("dmg") or 0) > 0:
            continue
        if category(mid) != cat:
            continue
        out.append(mid)
    return out


def candidates(dex: int) -> dict[str, str]:
    """grupo -> build (melee | ranged) de cada build ofensiva posible de esta especie: tres ataques de una categoría,
    con cada ataque como líder, y el potenciador de esa categoría."""
    out: dict[str, str] = {}
    for cat, buff in ATTACK_BUFF.items():
        for trio in itertools.combinations(decent_attacks(dex, cat), 3):
            for lead in trio:
                comps = [x for x in trio if x != lead]
                out["+".join([lead, *comps, buff])] = kind_of(list(trio))
    return out


@lru_cache(maxsize=1)
def space() -> dict[int, dict[str, str]]:
    return {dex: c for dex in sorted(_pokedex()) if (c := candidates(dex))}


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
    """Los dos mejores de cada forma y de cada build, por la criba."""
    spaces = space()
    pools: dict[tuple[int, str], dict[str, list[dict]]] = {}
    for (dex, group), row in rows.items():
        build = spaces.get(dex, {}).get(group)
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
