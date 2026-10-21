"""Fase 1: tier list de ataques. Cada ataque juega solo (sin grupo, con las cartas de estadística) en 6 Pokémon
de referencia de su clase, y la tabla compara los ataques entre sí sin que pese qué Pokémon los usa.

    python3 build/attack_tiers.py --sim     # corre el simulador (unas 75.000 partidas, ~2 min) y escribe la tabla
    python3 build/attack_tiers.py           # solo rehace data/attack_tiers.csv desde la salida ya guardada
    python3 build/attack_tiers.py --refs    # muestra los Pokémon de referencia y sale
    python3 build/attack_tiers.py --check   # falla si data/attack_tiers.csv no es lo que da la salida guardada

Referencias: los ataques físicos van en 6 atacantes físicos (pa > sa) y los especiales en 6 especiales. Son
Pokémon no legendarios con los dos ataques (pa y sa), vida y defensas cerca de la mediana de su clase, para que
un especial de referencia tenga el ataque físico de un especial típico y no el de un físico; repartidos en una rejilla
de tamaño (radio de colisión p10, p50, p90) por velocidad (p20, p80) y sin repetir tipos si se puede, para que
un ataque no gane solo porque le va bien a un cuerpo grande, a uno lento o a un tipo. Las elige pick_refs() con
los datos del juego, así que salen solas en cada versión nueva.

Puntuación: median_score del simulador (supervivencia por daño y bajas, simulator/sim-rs/src/stats.rs). Para
cada referencia se divide por la mediana de todos los ataques de su clase en esa misma referencia, y score_rel
es la media geométrica de esos 6 cocientes: 1,0 es un ataque normal de su clase, 1,5 rinde un 50 % más.
Tier dentro de cada clase por posición: S el 10 % mejor, A el 20 % siguiente, B el 30 %, C el 25 %, D el resto.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import json
import math
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator"
BIN = SIM / "sim-rs" / "target" / "release" / "pokesim"
V3 = SIM / "v3" / "v3_data.json"
GAME = ROOT / "data" / "game_stats.json"
OUT_DIR = SIM / "results" / "fase1"
TASKS = OUT_DIR / "attacks_tasks.txt"
RAW = OUT_DIR / "attacks_raw.csv"
TABLE = ROOT / "data" / "attack_tiers.csv"

SEEDS = 128  # con 32 un tercio de los ataques cambiaba de tier entre la primera y la segunda mitad de semillas
SEED0 = 0
FLAGS = ["--seconds", "900", "--status", "--terrain", "--xkinds"]
REFS_PER_CLASS = 6
CLASSES = ("physical", "special")
# (cuantil de radio, cuantil de velocidad) de cada casilla de la rejilla
GRID = [(r, s) for r in (0.1, 0.5, 0.9) for s in (0.2, 0.8)]
TYPE_PENALTY = 1.0  # por cada tipo que ya tiene otra referencia de la clase: que no salgan tres de fuego
TIER_SHARES = (("S", 0.10), ("A", 0.20), ("B", 0.30), ("C", 0.25), ("D", 0.15))
FLOOR = 0.01  # un ataque que no hace daño en una referencia cuenta como 1 % de la mediana


def load_v3() -> dict:
    return json.loads(V3.read_text(encoding="utf8"))


def attacker_class(mon: dict) -> str:
    return "physical" if mon["pa"] > mon["sa"] else "special"


def quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def pick_refs(dex: list[dict]) -> dict[str, list[dict]]:
    """6 Pokémon por clase: el más cercano a cada casilla de la rejilla tamaño × velocidad, con el resto de
    estadísticas lo más cerca posible de la mediana de su clase."""
    out = {}
    for cls in CLASSES:
        pool = [m for m in dex if attacker_class(m) == cls and not m["leg"]]
        med = {f: st.median(m[f] for m in pool) for f in ("pa", "sa", "hp", "df", "sd")}
        spread = {f: quantile([m[f] for m in pool], 0.75) - quantile([m[f] for m in pool], 0.25) or 1.0
                  for f in ("pa", "sa", "hp", "df", "sd", "r", "spd")}
        chosen: list[dict] = []
        for rq, sq in GRID:
            target = {"r": quantile([m["r"] for m in pool], rq), "spd": quantile([m["spd"] for m in pool], sq), **med}

            taken = {t for c in chosen for t in c["types"]}

            def dist(m: dict) -> float:
                return sum(abs(m[f] - target[f]) / spread[f] for f in target) + TYPE_PENALTY * len(taken & set(m["types"]))

            best = min((m for m in pool if m not in chosen), key=lambda m: (dist(m), m["dex"]))
            chosen.append(best)
        out[cls] = chosen
    return out


def attacks(v3: dict) -> dict[str, list[str]]:
    """Ataques del juego por clase: los que no son potenciadores y hacen daño a nivel 1."""
    game = json.loads(GAME.read_text(encoding="utf8"))["moves"]
    out: dict[str, list[str]] = {cls: [] for cls in CLASSES}
    for mid, move in sorted(v3["moves"].items()):
        level = move["levels"][0]
        if move["kind"] == "buff" or (level.get("buff") or 0) != 0 or not float(level.get("dmg") or 0) > 0:
            continue
        cat = game[mid]["cat"]
        if cat in out:
            out[cat].append(mid)
    return out


def run_sim(v3: dict) -> None:
    raise RuntimeError("Ranking 5a23d49 archived. Use the Rust candidates/evaluate diagnostics for ce57853; do not mix historical outputs with the new engine.")


def rel_scores(rows: list[dict], col: str, key: str = "move") -> dict[str, list[float]]:
    """move (o la columna `key`) -> cocientes frente a la mediana de su clase en cada referencia."""
    by_ref: dict[str, dict[str, float]] = {}
    for r in rows:
        by_ref.setdefault(r["dex"], {})[r[key]] = float(r[col])
    out: dict[str, list[float]] = {}
    for scores in by_ref.values():
        med = st.median(scores.values()) or 1.0
        for mid, s in scores.items():
            out.setdefault(mid, []).append(max(s / med, FLOOR))
    return out


def geomean(xs: list[float]) -> float:
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def tiers_for(n: int) -> list[str]:
    out: list[str] = []
    acc = 0.0
    for tier, share in TIER_SHARES:
        acc += share
        out += [tier] * (round(acc * n) - len(out))
    return out + ["D"] * (n - len(out))


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def build_table(v3: dict, out: Path = TABLE) -> None:
    game = json.loads(GAME.read_text(encoding="utf8"))["moves"]
    refs = pick_refs(v3["dex"])
    with RAW.open(encoding="utf8") as f:
        rows = list(csv.DictReader(f))
    by_move: dict[str, list[dict]] = {}
    for r in rows:
        by_move.setdefault(r["move"], []).append(r)

    out_rows = []
    print("estabilidad (primera mitad de semillas frente a la segunda):")
    for cls, mids in attacks(v3).items():
        ref_dex = {str(m["dex"]) for m in refs[cls]}
        cls_rows = [r for r in rows if r["dex"] in ref_dex and r["move"] in mids]
        rel = rel_scores(cls_rows, "median_score")
        half_a = rel_scores(cls_rows, "score_a")
        half_b = rel_scores(cls_rows, "score_b")
        ordered = sorted(mids, key=lambda m: (-geomean(rel[m]), m))
        rho = spearman([geomean(half_a[m]) for m in ordered], [geomean(half_b[m]) for m in ordered])
        tier_a = dict(zip(sorted(mids, key=lambda m: -geomean(half_a[m])), tiers_for(len(mids))))
        tier_b = dict(zip(sorted(mids, key=lambda m: -geomean(half_b[m])), tiers_for(len(mids))))
        moved = sum(tier_a[m] != tier_b[m] for m in mids)
        print(f"  {cls}: {len(mids)} ataques, Spearman {rho:.2f}, {moved} cambian de tier entre mitades")
        for rank, (mid, tier) in enumerate(zip(ordered, tiers_for(len(ordered))), 1):
            rs = by_move[mid]
            move = game[mid]
            out_rows.append({
                "class": cls, "tier": tier, "rank": rank, "move_id": mid, "name": move["name"], "name_en": move["en"],
                "type": move["type"], "kind": move["kind"],
                "score_rel": f"{geomean(rel[mid]):.3f}",
                "worst_ref": f"{min(rel[mid]):.3f}", "best_ref": f"{max(rel[mid]):.3f}",
                "median_s": f"{st.median(float(r['median_s']) for r in rs):.1f}",
                "median_kills": f"{st.median(float(r['median_kills']) for r in rs):.1f}",
                "median_dealt": f"{st.median(float(r['median_dealt']) for r in rs):.0f}",
            })
    ref_note = "; ".join(f"{cls}: " + ", ".join(f"{m['dex']} {m['name']}" for m in refs[cls]) for cls in CLASSES)
    with out.open("w", encoding="utf8", newline="") as f:
        f.write(f"# Fase 1 (build/attack_tiers.py): cada ataque solo, {SEEDS} semillas por referencia. "
                f"Referencias {ref_note}.\n")
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    if out == TABLE:
        print(f"escrito {TABLE.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 1: tier list de ataques.")
    parser.add_argument("--sim", action="store_true", help="Correr el simulador antes de escribir la tabla.")
    parser.add_argument("--refs", action="store_true", help="Mostrar los Pokémon de referencia y salir.")
    parser.add_argument("--check", action="store_true", help="Fallar si la tabla no es la que sale de la salida guardada.")
    args = parser.parse_args()
    v3 = load_v3()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "attack_tiers.csv"
            build_table(v3, out)
            if not filecmp.cmp(out, TABLE, shallow=False):
                sys.exit("data/attack_tiers.csv no coincide con simulator/results/fase1/attacks_raw.csv")
        print("attack_tiers.csv coincide con la salida guardada")
        return
    if args.refs:
        for cls, mons in pick_refs(v3["dex"]).items():
            for m in mons:
                atk = m["pa"] if cls == "physical" else m["sa"]
                print(f"{cls:9} {m['dex']:4} {m['name']:12} atk {atk} hp {m['hp']} spd {m['spd']} r {m['r']} "
                      f"df {m['df']} sd {m['sd']} {'/'.join(m['types'])}")
        for cls, mids in attacks(v3).items():
            print(f"{cls}: {len(mids)} ataques")
        return
    if args.sim:
        run_sim(v3)
    if not RAW.exists():
        sys.exit(f"falta {RAW.relative_to(ROOT)}: corre con --sim")
    build_table(v3)


if __name__ == "__main__":
    main()
