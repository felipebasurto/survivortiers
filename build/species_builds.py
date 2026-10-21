"""Fase 3: la mejor build cuerpo a cuerpo y la mejor a distancia de cada Pokémon, y el ranking que sale de ellas.

    python3 build/species_builds.py --sim     # corre las tres rondas y escribe las dos tablas (~2 h desde cero)
    python3 build/species_builds.py           # solo rehace las tablas desde la salida guardada
    python3 build/species_builds.py --check   # falla si las tablas no son lo que da la salida guardada

Necesita las fases 1 y 2 (data/attack_tiers.csv, simulator/results/fase2/). Cada especie juega con sus propios ataques
(pool y ataque inicial, build/builds.py decent_attacks) y todos sus grupos posibles (builds.candidates: cualquier
categoría, cualquier ataque delante, cualquier potenciador que suba algún ataque, Danza Dragón si la aprende, las
tres formas de cuatro huecos). El grupo entero está vinculado desde el principio (`--bonded`), como en la fase 2.

Son unos 5.800 grupos por especie, así que no se simulan todos:
1. Un modelo aditivo, ajustado en la ronda 1 de la fase 2 de la clase de la especie (pa > sa: física), da a cada
   grupo una cifra prevista: un término por ataque delante, uno por ataque detrás y uno por forma y potenciador
   (cuántos ataques sube). Un ataque que la fase 2 no probó toma el término que le da su score_rel de la fase 1, con
   la recta que esos términos siguen frente a la fase 1 en los ataques de su misma categoría, y nunca más que el
   peor término probado de su categoría y papel (en la fase 1 todos los no probados quedaron por debajo).
   Comprobado en la fase 2: los 5 mejores grupos reales de cada build quedan entre los puestos 24 y 253 de ~5.400.
2. Ronda A: para cada especie y build, los TOP_A mejores previstos de cada mezcla (solo físicos, solo especiales,
   mezclados), jugados por la propia especie. El modelo no decide entre categorías: lo decide la especie.
   Dentro de su mezcla el modelo apenas ordena: con 10 por mezcla el ganador salía en cualquier puesto casi por igual,
   y en una muestra de 50 especies alargar la lista a 30 mejoró la mejor build de 9 de ellas más de un 5 % (con
   semillas nuevas). Por eso TOP_A es 30.
3. Ronda B: los TOP_B mejores de la ronda A, con más semillas y nuevas.
4. Ronda C: el mejor de la ronda B, con semillas nuevas otra vez. Su cifra es la publicada, sin la suerte que lo
   eligió.

Variantes (`--variants`, después de la búsqueda principal): para cada build, otra build del mismo tipo que cambia
una cosa, con el mismo embudo de tres rondas y las mismas semillas:
- agresiva: sin potenciador de defensa, cuando la build lleva uno;
- cobertura: la que deja en la mitad o menos los enemigos que resisten todos sus ataques (build/coverage.py), cuando
  la build tiene al menos COVER_MIN.
Su ronda A son los grupos de la ronda A principal que cumplen la condición más los TOP_V mejores previstos que la
cumplen (el modelo de arriba).

Desempate (`--promote`, después de las variantes): si una variante puntúa más que su build en la ronda C, las dos
vuelven a jugar con semillas nuevas (ronda D, ROUND_D). Si la variante gana también ahí, pasa a ser la build, con las
cifras de la ronda D; si no, la build se queda con las de la ronda C. Las parejas quedan fijadas en
simulator/results/fase3/rD_pairs.csv, y las variantes se vuelven a buscar para las builds nuevas.

Regla de tipos (`--rule`, después del desempate): toda build lleva el potenciador de ataque que sube al menos uno de
sus ataques del tipo del Pokémon, y al menos dos ataques de su tipo (uno de cada tipo si tiene dos). La simulación
favorecía ataques Normal porque cada pool tiene muchos y en los empates el azar elegía uno de ellos. Si la build no
cumple la regla, se elige entre los grupos que la cumplen y ya jugaron la ronda A (la principal o la de variantes),
con el mismo embudo: los TOP_B mejores a la ronda B y el mejor a la C, reutilizando las partidas ya jugadas. Las
elegidas quedan en simulator/results/fase3/rule_picks.csv. Las variantes también cumplen la regla.

Ranking: median_score de la ronda C (supervivencia, daño y bajas; simulator/sim-rs/src/stats.rs) de la mejor de las
dos builds. Tiers con los cortes de data/tiers.json.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import functools
import hashlib
import math
import statistics as st
import sys
import tempfile
from pathlib import Path

import attack_tiers as at
import bond_tiers as bt
import builds
import coverage
import picks
import tiers

ROOT = at.ROOT
SIM = at.SIM
OUT_DIR = SIM / "results" / "fase3"
BUILDS_TABLE = ROOT / "data" / "species_builds.csv"
RANK_TABLE = ROOT / "data" / "ranking_fase3.csv"
VARIANT_TABLE = ROOT / "data" / "species_variants.csv"

SECONDS = "900"
TOP_A = 30  # por especie, build y mezcla de categorías
TOP_B = 4  # por especie y build
ROUNDS = ((4, 0), (32, 100), (128, 1000))  # (semillas, seed0) de las rondas A, B y C
ROUND_D = (128, 5000)  # el desempate entre una build y la variante que la supera en la ronda C
SEEDS = (*ROUNDS, ROUND_D)
MIXES = ("physical", "special", "mixed")
VARIANTS = ("aggro", "cover")
COVER_MIN = 40  # especies enemigas (de 862) que resisten todos los ataques de la build
TOP_V = 15  # grupos previstos nuevos por build y variante


def only_path(k: int, tag: str = "r") -> Path:
    return OUT_DIR / f"{tag}{'ABCD'[k]}_only.txt"


def raw_path(k: int, tag: str = "r") -> Path:
    return OUT_DIR / f"{tag}{'ABCD'[k]}_raw.csv"


def mix_of(attacks: list[str]) -> str:
    cats = {builds._game_moves()[a]["cat"] for a in attacks}
    return cats.pop() if len(cats) == 1 else "mixed"


def features(group: str) -> dict[str, float]:
    attacks, buff, fourth = picks.split_group(group)
    side = picks.attack_buff_side()
    f = {"L:" + attacks[0]: 1.0}
    for a in attacks[1:]:
        f["C:" + a] = f.get("C:" + a, 0.0) + 1.0
    raised = sum(builds._game_moves()[a]["cat"] == side[buff] for a in attacks) if buff else 0
    f[f"S:{len(attacks)}|{buff}|{raised}|{fourth}"] = 1.0
    return f


class Model:
    """log(score_rel) previsto de un grupo, para una clase. Mínimos cuadrados sobre la ronda 1 de la fase 2."""

    def __init__(self, cls: str, rounds: bt.Rounds, phase1: dict[str, dict]) -> None:
        import numpy as np

        y = {g: math.log(at.geomean(v)) for g, v in rounds.rel(0, cls).items()}
        names = sorted(y)
        keys = sorted({k for g in names for k in features(g)})
        ix = {k: i for i, k in enumerate(keys)}
        x = np.zeros((len(names), len(keys) + 1))
        for i, g in enumerate(names):
            for k, v in features(g).items():
                x[i, ix[k]] = v
            x[i, -1] = 1.0
        w, *_ = np.linalg.lstsq(x, np.array([y[g] for g in names]), rcond=None)
        self.w = {k: float(w[i]) for k, i in ix.items()}
        self.w["1"] = float(w[-1])
        # recta término ~ log(score_rel de la fase 1), por papel (delante o detrás) y categoría
        self.line: dict[tuple[str, str], tuple[float, float]] = {}
        for role in ("L", "C"):
            for cat in at.CLASSES:
                pts = [(math.log(float(phase1[k[2:]]["score_rel"])), v) for k, v in self.w.items()
                       if k.startswith(role + ":") and phase1[k[2:]]["class"] == cat]
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                mx, my = st.mean(xs), st.mean(ys)
                sxx = sum((a - mx) ** 2 for a in xs) or 1.0
                slope = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sxx
                self.line[(role, cat)] = (my - slope * mx, slope)
        self.phase1 = phase1

    def term(self, key: str) -> float:
        if key in self.w:
            return self.w[key]
        if key.startswith("S:"):
            return min(v for k, v in self.w.items() if k.startswith("S:"))
        role, mid = key[0], key[2:]
        cat = self.phase1[mid]["class"]
        a, b = self.line[(role, cat)]
        # La recta sale de los mejores ataques de la fase 1 y puede ser plana; un ataque que la fase 2 no probó es
        # peor en la fase 1 que los que sí, así que no puede valer más que el peor de ellos.
        floor = min(v for k, v in self.w.items() if k.startswith(role + ":") and self.phase1[k[2:]]["class"] == cat)
        return min(a + b * math.log(float(self.phase1[mid]["score_rel"])), floor)

    def predict(self, group: str) -> float:
        return self.w["1"] + sum(v * self.term(k) for k, v in features(group).items())


def models() -> dict[str, Model]:
    phase1 = {r["move_id"]: r for r in bt.attack_rows()}
    rounds = bt.load_rounds()
    return {cls: Model(cls, rounds, phase1) for cls in at.CLASSES}


def shortlist() -> dict[tuple[int, str], list[str]]:
    """(dex, build) -> grupos de la ronda A."""
    ms = models()
    out: dict[tuple[int, str], list[str]] = {}
    for mon in at.load_v3()["dex"]:
        model = ms[at.attacker_class(mon)]
        buckets: dict[tuple[str, str], list[tuple[float, str]]] = {}
        for g, build in builds.candidates(mon["dex"]).items():
            attacks = picks.split_group(g)[0]
            buckets.setdefault((build, mix_of(attacks)), []).append((-model.predict(g), g))
        for (build, _), items in sorted(buckets.items()):
            out.setdefault((mon["dex"], build), []).extend(g for _, g in sorted(items)[:TOP_A])
    return out


def load(path: Path) -> dict[tuple[int, str], dict]:
    with path.open(encoding="utf8") as f:
        return {(int(r["dex"]), r["group"]): r for r in csv.DictReader(f)}


def order(row: dict) -> tuple:
    return picks.group_order(row)


def advance(rows: dict[tuple[int, str], dict], keys: dict[tuple[int, str], list[str]], n: int) -> dict[tuple[int, str], list[str]]:
    return {key: [r["group"] for r in sorted((rows[(key[0], g)] for g in gs), key=order)[:n]] for key, gs in keys.items()}


def fingerprint(k: int) -> str:
    """Huella de lo que decide el resultado de un grupo: el motor, los datos del juego y las semillas de la ronda."""
    h = hashlib.sha256(repr((SEEDS[k], SECONDS)).encode())
    for path in sorted((SIM / "sim-rs" / "src").rglob("*")) + [SIM / "v3" / "v3_data.json"]:
        if path.is_file():
            h.update(str(path.relative_to(SIM)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def run_round(k: int, keys: dict[tuple[int, str], list[str]], tag: str = "r") -> None:
    """Simula los grupos de la ronda k que faltan. Un grupo con el mismo motor, datos y semillas da la misma fila,
    así que las filas guardadas con la misma huella se reutilizan (las variantes, también las de la búsqueda
    principal); si la huella cambia, la ronda se hace entera."""
    seeds, seed0 = SEEDS[k]
    need = {(dex, g) for (dex, _), gs in keys.items() for g in gs}
    have: dict[tuple[int, str], dict] = {}
    for t in dict.fromkeys((tag, "r", "v")):
        stamp = raw_path(k, t).with_suffix(".fingerprint")
        if raw_path(k, t).exists() and stamp.exists() and stamp.read_text().strip() == fingerprint(k):
            have.update({key: r for key, r in load(raw_path(k, t)).items() if key in need and key not in have})
    todo = sorted(need - set(have))
    print(f"ronda {tag}{'ABCD'[k]}: {len(need)} grupos, {len(have)} ya jugados, {len(todo)} x {seeds} semillas = "
          f"{len(todo) * seeds} partidas", flush=True)
    if todo:
        only_path(k, tag).write_text("".join(f"{dex}|{g}\n" for dex, g in todo), encoding="utf8")
        fresh = OUT_DIR / f"{tag}{'ABCD'[k]}_new.csv"
        bt.synergy(only_path(k, tag), fresh, seeds, seed0)
        have.update(load(fresh))
        fresh.unlink()
    with raw_path(k, tag).open("w", encoding="utf8", newline="") as f:
        rows = [have[key] for key in sorted(need)]
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    raw_path(k, tag).with_suffix(".fingerprint").write_text(fingerprint(k) + "\n", encoding="utf8")


def run_sim() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keys = shortlist()
    for k in range(len(ROUNDS)):
        run_round(k, keys)
        if k + 1 < len(ROUNDS):
            keys = advance(load(raw_path(k)), keys, TOP_B if k == 0 else 1)


PAIRS = OUT_DIR / "rD_pairs.csv"


def searched_keys() -> dict[tuple[int, str], str]:
    """(dex, build) -> el grupo que sale de las rondas A, B y C."""
    rows = [load(raw_path(k)) for k in range(2)]
    keys_a: dict[tuple[int, str], list[str]] = {}
    for (dex, g) in rows[0]:
        keys_a.setdefault((dex, builds._kind(picks.split_group(g)[0])), []).append(g)
    keys_c = advance(rows[1], advance(rows[0], keys_a, TOP_B), 1)
    return {key: gs[0] for key, gs in keys_c.items()}


def pairs() -> dict[tuple[int, str], tuple[str, str]]:
    """(dex, build) -> (build buscada, variante que la retó), de rD_pairs.csv."""
    if not PAIRS.exists():
        return {}
    with PAIRS.open(encoding="utf8") as f:
        return {(int(r["dex"]), r["build"]): (r["main"], r["challenger"]) for r in csv.DictReader(f)}


def promoted() -> dict[tuple[int, str], str]:
    """(dex, build) -> la variante que ganó también el desempate de la ronda D."""
    if not pairs():
        return {}
    d = load(raw_path(3))
    return {key: alt for key, (main, alt) in pairs().items() if order(d[(key[0], alt)]) < order(d[(key[0], main)])}


RULE_PICKS = OUT_DIR / "rule_picks.csv"


@functools.lru_cache(maxsize=None)
def _types(dex: int) -> tuple[str, ...]:
    return tuple(next(m for m in at.load_v3()["dex"] if m["dex"] == dex)["types"])


def rule_ok(dex: int, group: str) -> bool:
    """El potenciador de ataque sube al menos un ataque de su tipo, y lleva dos ataques de su tipo (uno de cada tipo
    si tiene dos)."""
    attacks, buff, _ = picks.split_group(group)
    types = _types(dex)
    own = [a for a in attacks if coverage.move_type(a) in types]
    if buff is None or picks.attack_buff_side()[buff] not in {builds._game_moves()[a]["cat"] for a in own}:
        return False
    if len(types) == 2:
        return {coverage.move_type(a) for a in own} == set(types)
    return len(own) >= 2


def ruled() -> dict[tuple[int, str], str]:
    """(dex, build) -> el grupo que cumple la regla de tipos, de rule_picks.csv."""
    if not RULE_PICKS.exists():
        return {}
    with RULE_PICKS.open(encoding="utf8") as f:
        return {(int(r["dex"]), r["build"]): r["group"] for r in csv.DictReader(f)}


def main_keys() -> dict[tuple[int, str], str]:
    """(dex, build) -> el grupo publicado: el de la búsqueda, la variante que ganó el desempate o el elegido por la
    regla de tipos."""
    return {**searched_keys(), **promoted(), **ruled()}


def main_rows() -> dict[tuple[int, str], tuple[str, dict]]:
    """(dex, build) -> (grupo publicado, sus cifras): las de la ronda C de la regla si la build no la cumplía, las de
    la ronda D si ganó el desempate, si no las de la C."""
    won, rule = promoted(), ruled()
    c = load(raw_path(2))
    d = load(raw_path(3)) if won else {}
    q = load(raw_path(2, "q")) if rule else {}

    def row(key: tuple[int, str], g: str) -> dict:
        if key in rule:
            return q[(key[0], g)]
        return d[(key[0], g)] if key in won else c[(key[0], g)]
    return {key: (g, row(key, g)) for key, g in main_keys().items()}


def run_rule() -> None:
    """Las builds que no cumplen la regla de tipos eligen entre los grupos que la cumplen (rondas B y C)."""
    if RULE_PICKS.exists():
        sys.exit(f"{RULE_PICKS.relative_to(ROOT)} ya existe: bórralo para volver a elegir")
    rows_a = {**load(raw_path(0)), **load(raw_path(0, "v"))}
    played: dict[int, list[str]] = {}
    for dex, g in rows_a:
        played.setdefault(dex, []).append(g)
    keys_a = {}
    for (dex, build), main in sorted(main_keys().items()):
        if rule_ok(dex, main):
            continue
        gs = sorted(g for g in played.get(dex, []) if builds._kind(picks.split_group(g)[0]) == build and rule_ok(dex, g))
        if gs:
            keys_a[(dex, build)] = gs
    keys_b = advance(rows_a, keys_a, TOP_B)
    run_round(1, keys_b, "q")
    keys_c = advance(load(raw_path(1, "q")), keys_b, 1)
    run_round(2, keys_c, "q")
    with RULE_PICKS.open("w", encoding="utf8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dex", "build", "group"])
        w.writerows([dex, b, gs[0]] for (dex, b), gs in sorted(keys_c.items()))


def run_promote() -> None:
    """Fija las parejas (variante que supera a su build en la ronda C) y juega su desempate."""
    if PAIRS.exists():
        sys.exit(f"{PAIRS.relative_to(ROOT)} ya existe: bórralo para volver a elegir las parejas")
    c, vc = load(raw_path(2)), load(raw_path(2, "v"))
    found: dict[tuple[int, str], tuple[str, str]] = {}
    for row in variant_rows():
        key, main = (row["dex"], row["build"]), row["main"]
        if order(vc[(key[0], row["group"])]) < order(c[(key[0], main)]):
            cur = found.get(key)
            if cur is None or order(vc[(key[0], row["group"])]) < order(vc[(key[0], cur[1])]):
                found[key] = (main, row["group"])
    with PAIRS.open("w", encoding="utf8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dex", "build", "main", "challenger"])
        w.writerows([dex, b, m, a] for (dex, b), (m, a) in sorted(found.items()))
    run_round(3, {key: [m, a] for key, (m, a) in found.items()})


def resist(group: str) -> int:
    return _resist(tuple(coverage.attack_types(group.split("+"))))


@functools.lru_cache(maxsize=None)
def _resist(types: tuple[str, ...]) -> int:
    return coverage.of_types(list(types))["resist"]


def wants(variant: str, main: str) -> bool:
    if variant == "aggro":
        return picks.split_group(main)[2] is not None
    return resist(main) >= COVER_MIN


def fits(variant: str, main: str, group: str, dex: int) -> bool:
    if not rule_ok(dex, group):
        return False
    if variant == "aggro":
        return picks.split_group(group)[2] is None
    return 2 * resist(group) <= resist(main)


def variant_pools(extra: dict[tuple[int, str], dict] | None = None) -> dict[tuple[int, str], list[str]]:
    """(dex, "build:variante") -> su ronda A: los grupos jugados (ronda A principal y de variantes) del mismo tipo de
    build que cumplen la condición."""
    played: dict[int, set[str]] = {}
    for (dex, g) in [*load(raw_path(0)), *(extra or {})]:
        played.setdefault(dex, set()).add(g)
    out: dict[tuple[int, str], list[str]] = {}
    for (dex, build), main in sorted(main_keys().items()):
        for v in VARIANTS:
            if not wants(v, main):
                continue
            gs = sorted(g for g in played.get(dex, ()) if g != main and builds._kind(picks.split_group(g)[0]) == build
                        and fits(v, main, g, dex))
            if gs:
                out[(dex, f"{build}:{v}")] = gs
    return out


def run_variants() -> None:
    ms = models()
    v3 = {m["dex"]: m for m in at.load_v3()["dex"]}
    played = load(raw_path(0))
    keys: dict[tuple[int, str], list[str]] = {}
    for (dex, build), main in sorted(main_keys().items()):
        model = ms[at.attacker_class(v3[dex])]
        cands = [g for g, b in builds.candidates(dex).items() if b == build and g != main]
        for v in VARIANTS:
            if wants(v, main):
                new = sorted((-model.predict(g), g) for g in cands if (dex, g) not in played and fits(v, main, g, dex))
                keys[(dex, f"{build}:{v}")] = [g for _, g in new[:TOP_V]]
    run_round(0, keys, "v")
    pools = variant_pools(load(raw_path(0, "v")))
    rows_a = {**load(raw_path(0)), **load(raw_path(0, "v"))}
    keys = advance(rows_a, pools, TOP_B)
    run_round(1, keys, "v")
    keys = advance(load(raw_path(1, "v")), keys, 1)
    run_round(2, keys, "v")


def variant_rows() -> list[dict]:
    rows_a = {**load(raw_path(0)), **load(raw_path(0, "v"))}
    pools = variant_pools(load(raw_path(0, "v")))
    keys_c = advance(load(raw_path(1, "v")), advance(rows_a, pools, TOP_B), 1)
    final = load(raw_path(2, "v"))
    mains = main_keys()
    out_rows = []
    for (dex, tag), (g,) in sorted(keys_c.items()):
        build, variant = tag.split(":")
        r = final[(dex, g)]
        out_rows.append({
            "dex": dex, "build": build, "variant": variant, "group": g, "main": mains[(dex, build)],
            "resist": resist(g), "main_resist": resist(mains[(dex, build)]),
            "median_s": r["median_s"], "median_kills": r["median_kills"], "median_dealt": r["median_dealt"],
            "median_score": r["median_score"], "score_lo": r["score_lo"], "score_hi": r["score_hi"],
        })
    return out_rows


def variant_table(out: Path = VARIANT_TABLE) -> None:
    out_rows = variant_rows()
    with out.open("w", encoding="utf8", newline="") as f:
        f.write(f"# Fase 3, variantes (build/species_builds.py --variants): agresiva (sin potenciador de defensa) y "
                f"cobertura (la mitad o menos de enemigos que resisten); {ROUNDS[2][0]} semillas.\n")
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    if out == VARIANT_TABLE:
        print(f"escrito {VARIANT_TABLE.relative_to(ROOT)}: {len(out_rows)} variantes")


def build_tables(builds_out: Path = BUILDS_TABLE, rank_out: Path = RANK_TABLE) -> None:
    v3 = {m["dex"]: m for m in at.load_v3()["dex"]}
    names = builds._game_moves()
    published = {}
    out_rows = []
    for (dex, build), (g, r) in sorted(main_rows().items()):
        published[(dex, g)] = r
        attacks, buff, fourth = picks.split_group(g)
        out_rows.append({
            "dex": dex, "name": v3[dex]["name"], "build": build, "group": g,
            "attacks": " + ".join(names[a]["name"] for a in attacks),
            "boosts": " + ".join(names[b]["name"] for b in (buff, fourth) if b),
            "mix": mix_of(attacks), "seeds": ROUNDS[2][0],
            "median_s": r["median_s"], "median_kills": r["median_kills"], "median_dealt": r["median_dealt"],
            "median_score": r["median_score"], "score_lo": r["score_lo"], "score_hi": r["score_hi"],
        })
    with builds_out.open("w", encoding="utf8", newline="") as f:
        f.write(f"# Fase 3 (build/species_builds.py): la mejor build de cada especie y tipo, con el grupo vinculado "
                f"desde el principio; cifras de {ROUNDS[2][0]} semillas que no se usaron para elegirla (ronda C, o la D "
                f"si una variante ganó el desempate).\n")
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)

    best: dict[int, dict] = {}
    other: dict[int, dict] = {}
    for row in out_rows:
        cur = best.get(row["dex"])
        if cur is None or float(row["median_score"]) > float(cur["median_score"]):
            if cur is not None:
                other[row["dex"]] = cur
            best[row["dex"]] = row
        else:
            other[row["dex"]] = row
    ranked = sorted(best.values(), key=lambda r: (-float(r["median_score"]), r["dex"]))
    halves = {d: (float(published[(d, r["group"])]["score_a"]), float(published[(d, r["group"])]["score_b"]))
              for d, r in best.items()}
    rank_rows = []
    for i, r in enumerate(ranked, 1):
        o = other.get(r["dex"])
        rank_rows.append({
            "rank": i, "dex": r["dex"], "name": r["name"], "tier": tiers.TIER_OF[i], "build": r["build"],
            "group": r["group"], "median_score": r["median_score"], "score_lo": r["score_lo"], "score_hi": r["score_hi"],
            "median_s": r["median_s"], "other_build": o["build"] if o else "", "other_score": o["median_score"] if o else "",
        })
    rho = at.spearman([halves[r["dex"]][0] for r in ranked], [halves[r["dex"]][1] for r in ranked])
    top_a = set(sorted(halves, key=lambda d: -halves[d][0])[:30])
    top_b = set(sorted(halves, key=lambda d: -halves[d][1])[:30])
    print(f"ranking: {len(ranked)} especies; mitades de semillas de la ronda C: Spearman {rho:.3f}, "
          f"top 30 comparten {len(top_a & top_b)}")
    with rank_out.open("w", encoding="utf8", newline="") as f:
        f.write("# Fase 3 (build/species_builds.py): ranking por la mejor build de cada especie (median_score de "
                f"{ROUNDS[2][0]} semillas). Tiers de data/tiers.json.\n")
        w = csv.DictWriter(f, fieldnames=list(rank_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rank_rows)
    if builds_out == BUILDS_TABLE:
        print(f"escrito {BUILDS_TABLE.relative_to(ROOT)} y {RANK_TABLE.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 3: build óptima por Pokémon y ranking.")
    parser.add_argument("--sim", action="store_true", help="Correr el simulador antes de escribir las tablas.")
    parser.add_argument("--variants", action="store_true", help="Simular las variantes agresiva y de cobertura.")
    parser.add_argument("--rule", action="store_true",
                        help="Regla de tipos: las builds que no la cumplen eligen entre las que sí, y variantes nuevas.")
    parser.add_argument("--promote", action="store_true",
                        help="Desempate de las variantes que superan a su build, y variantes de las builds nuevas.")
    parser.add_argument("--check", action="store_true", help="Fallar si las tablas no son las que sale de la salida guardada.")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            b, r, v = Path(tmp) / "b.csv", Path(tmp) / "r.csv", Path(tmp) / "v.csv"
            build_tables(b, r)
            variant_table(v)
            if not all(filecmp.cmp(a, z, shallow=False) for a, z in
                       ((b, BUILDS_TABLE), (r, RANK_TABLE), (v, VARIANT_TABLE))):
                sys.exit("species_builds.csv, ranking_fase3.csv o species_variants.csv no coinciden con "
                         "simulator/results/fase3/")
        print("species_builds.csv, ranking_fase3.csv y species_variants.csv coinciden con la salida guardada")
        return
    if args.sim:
        run_sim()
    if not all(raw_path(k).exists() for k in range(len(ROUNDS))):
        sys.exit(f"falta la salida de {OUT_DIR.relative_to(ROOT)}: corre con --sim")
    if args.variants:
        run_variants()
    if args.promote:
        run_promote()
        run_variants()
    if args.rule:
        run_rule()
        run_variants()
    build_tables()
    if all(raw_path(k, "v").exists() for k in range(len(ROUNDS))):
        variant_table()


if __name__ == "__main__":
    main()
