"""Fase 2: tier list de vínculos. Grupos de cuatro huecos con los mejores ataques de la fase 1, jugados por los 6
Pokémon de referencia de cada clase (build/attack_tiers.py), para ver qué combinaciones rinden juntas.

    python3 build/bond_tiers.py --sim     # corre las tres rondas (~30 min) y escribe data/bond_tiers.csv
    python3 build/bond_tiers.py           # solo rehace la tabla desde la salida guardada
    python3 build/bond_tiers.py --check   # falla si data/bond_tiers.csv no es lo que da la salida guardada

Necesita data/attack_tiers.csv (fase 1). Los grupos son los de build/builds.py variants(), sin reglas de clase:
cualquier mezcla de categorías, cualquier potenciador de ataque que suba algún ataque del grupo, y las tres formas
que llenan los cuatro huecos (dos ataques + ataque + defensa, tres + ataque, tres + defensa). Las dos clases juegan
los mismos grupos, cada una en sus 6 referencias. Un grupo es cuerpo a cuerpo si lleva algún ataque `melee`.

El grupo entero está vinculado desde el principio (`pokesim synergy --bonded`: sin fisuras, con jefes y todos los
tipos de ataque). Con los vínculos de fisura el bot muere hacia los 140 s, antes de la segunda fisura, y el tercer
ataque no llegaba a dispararse: Bucle Arena + Magnitud + cualquier tercero daba la misma partida.

Ataques candidatos (lo único que se acota, por coste): los TOP mejores de cada categoría en la fase 1, más los que
solos valen poco pero dependen del grupo: las embestidas (invulnerables al lanzarse) e Infortunio (×1,7 contra un
rival con estado); y cuerpo a cuerpo hasta MELEE_MIN, para que la build melee tenga de dónde elegir. Abre el grupo
el ataque con mejor score_rel en la fase 1.

Tres rondas, cada una con semillas que las anteriores no usaron (así la suerte que subió a un grupo no infla su
cifra): ROUNDS da semillas y seed0, KEEP la parte de cada clase y build que pasa a la siguiente. A la ronda 2 pasan
además AUDIT grupos descartados al azar por clase, para medir si el corte de la ronda 1 tira grupos buenos.

Puntuación: median_score de cada grupo dividido por la mediana de todos los grupos de la clase en esa referencia en la
ronda 1, y media geométrica de las 6 referencias. No se compara con la fase 1. En la tabla van primero los grupos de
la ronda 3 (por su cifra de la ronda 3), luego los de la 2 y luego el resto; la columna `seeds` (por referencia) dice
de qué ronda es cada cifra, y solo se comparan cifras con las mismas semillas. Tier dentro de cada clase y build,
con los mismos cortes que la fase 1.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import itertools
import math
import random
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

import attack_tiers as at
import builds
import picks

ROOT = at.ROOT
SIM = at.SIM
OUT_DIR = SIM / "results" / "fase2"
TABLE = ROOT / "data" / "bond_tiers.csv"

SECONDS = "900"
TOP = 8
MELEE_MIN = 5
ALWAYS_KINDS = frozenset({"dash"})
ALWAYS_MOVES = frozenset({"hex"})
ROUNDS = ((2, 0), (16, 100), (64, 1000))  # (semillas por referencia, seed0)
KEEP = (0.08, 0.15)  # parte de cada clase y build que pasa de la ronda 1 a la 2 y de la 2 a la 3
AUDIT = 100
AUDIT_SEED = 0


def only_path(k: int) -> Path:
    return OUT_DIR / f"r{k}_only.txt"


def raw_path(k: int) -> Path:
    return OUT_DIR / f"r{k}_raw.csv"


def attack_rows() -> list[dict]:
    with at.TABLE.open(encoding="utf8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def candidates(rows: list[dict]) -> list[dict]:
    """Filas de la fase 1 que entran en la búsqueda, de mayor a menor score_rel."""
    by_rank = sorted(rows, key=lambda r: int(r["rank"]))
    chosen: list[dict] = []
    for cls in at.CLASSES:
        chosen += [r for r in by_rank if r["class"] == cls][:TOP]
    melee = [r for r in sorted(rows, key=lambda r: -float(r["score_rel"])) if r["kind"] == "melee" and r not in chosen]
    chosen += melee[:max(0, MELEE_MIN - sum(r["kind"] == "melee" for r in chosen))]
    chosen += [r for r in by_rank if r not in chosen and (r["kind"] in ALWAYS_KINDS or r["move_id"] in ALWAYS_MOVES)]
    return sorted(chosen, key=lambda r: (-float(r["score_rel"]), r["move_id"]))


def groups(cands: list[dict]) -> dict[str, dict]:
    """nombre del grupo -> {attacks, shape, build}. El orden de `cands` pone delante al mejor ataque."""
    ids = [r["move_id"] for r in cands]
    melee = {r["move_id"] for r in cands if r["kind"] == "melee"}
    out: dict[str, dict] = {}
    for k in (2, 3):
        for attacks in itertools.combinations(ids, k):
            build = "melee" if melee & set(attacks) else "ranged"
            for g in builds.variants(attacks):
                out[g] = {"attacks": attacks, "shape": picks.shape_of(g), "build": build}
    return out


def synergy(only: Path, out: Path, seeds: int, seed0: int) -> None:
    subprocess.run([str(at.BIN), "synergy", "--explicit", "--bonded", "--seeds", str(seeds), "--seed0", str(seed0),
                    "--seconds", SECONDS, "--only", str(only), "--out", str(out)], cwd=SIM, check=True)


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf8") as f:
        return list(csv.DictReader(f))


class Rounds:
    """Lo que dejan guardado las rondas: las filas de cada una y, por clase, qué grupos jugó cada ronda."""

    def __init__(self) -> None:
        self.attacks = {r["move_id"]: r for r in attack_rows()}
        self.gs = groups(candidates(list(self.attacks.values())))
        self.refs = {cls: {str(m["dex"]) for m in ms} for cls, ms in at.pick_refs(at.load_v3()["dex"]).items()}
        self.rows: list[list[dict]] = []
        self.meds: dict[str, float] = {}

    def add(self, rows: list[dict]) -> None:
        self.rows.append(rows)
        if len(self.rows) == 1:
            by_ref: dict[str, list[float]] = {}
            for r in rows:
                by_ref.setdefault(r["dex"], []).append(float(r["median_score"]))
            self.meds = {dex: st.median(v) or 1.0 for dex, v in by_ref.items()}

    def rel(self, k: int, cls: str, col: str = "median_score") -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for r in self.rows[k]:
            if r["dex"] in self.refs[cls]:
                out.setdefault(r["group"], []).append(max(float(r[col]) / self.meds[r["dex"]], at.FLOOR))
        return out

    def played(self, k: int, cls: str) -> set[str]:
        return {r["group"] for r in self.rows[k] if r["dex"] in self.refs[cls]}

    def next_set(self, k: int) -> dict[str, list[str]]:
        """clase -> grupos que pasan de la ronda k a la k+1 (más la muestra de control tras la ronda 1)."""
        out: dict[str, list[str]] = {}
        for cls in at.CLASSES:
            score = {g: at.geomean(v) for g, v in self.rel(k, cls).items()}
            keep: list[str] = []
            for build in ("melee", "ranged"):
                names = sorted((g for g in score if self.gs[g]["build"] == build), key=lambda g: (-score[g], g))
                keep += names[:math.ceil(KEEP[k] * len(names))]
            if k == 0:
                dropped = sorted(set(score) - set(keep))
                keep += random.Random(f"{AUDIT_SEED}{cls}").sample(dropped, min(AUDIT, len(dropped)))
            out[cls] = sorted(keep)
        return out

    def audit(self, cls: str) -> list[str]:
        """Los grupos de control: jugaron la ronda 2 sin haber pasado el corte de la ronda 1."""
        score = {g: at.geomean(v) for g, v in self.rel(0, cls).items()}
        passed: set[str] = set()
        for build in ("melee", "ranged"):
            names = sorted((g for g in score if self.gs[g]["build"] == build), key=lambda g: (-score[g], g))
            passed |= set(names[:math.ceil(KEEP[0] * len(names))])
        return sorted(self.played(1, cls) - passed)


def run_sim() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not at.BIN.exists():
        subprocess.run(["cargo", "build", "--release", "--manifest-path", str(SIM / "sim-rs" / "Cargo.toml")], check=True)
    rounds = Rounds()
    todo = {cls: sorted(rounds.gs) for cls in at.CLASSES}
    for k, (seeds, seed0) in enumerate(ROUNDS):
        lines = sorted(f"{dex}|{g}" for cls, gs in todo.items() for g in gs for dex in rounds.refs[cls])
        only_path(k + 1).write_text("\n".join(lines) + "\n", encoding="utf8")
        print(f"ronda {k + 1}: {len(lines) // 6} grupos-clase x 6 referencias x {seeds} semillas = "
              f"{len(lines) * seeds} partidas", flush=True)
        synergy(only_path(k + 1), raw_path(k + 1), seeds, seed0)
        rounds.add(load(raw_path(k + 1)))
        if k + 1 < len(ROUNDS):
            todo = rounds.next_set(k)


def load_rounds() -> Rounds:
    rounds = Rounds()
    for k in range(len(ROUNDS)):
        rounds.add(load(raw_path(k + 1)))
    return rounds


def build_table(out: Path = TABLE) -> None:
    rounds = load_rounds()
    attacks, gs = rounds.attacks, rounds.gs
    out_rows = []
    print("estabilidad (primera mitad de semillas frente a la segunda) y control del corte de la ronda 1:")
    for cls in at.CLASSES:
        rel = [rounds.rel(k, cls) for k in range(len(ROUNDS))]
        reach = {g: max(k for k in range(len(ROUNDS)) if g in rel[k]) for g in rel[0]}
        rows_of: dict[tuple[int, str], list[dict]] = {}
        for k, rows in enumerate(rounds.rows):
            for r in rows:
                if r["dex"] in rounds.refs[cls]:
                    rows_of.setdefault((k, r["group"]), []).append(r)
        audit = set(rounds.audit(cls))
        third = {g for g in reach if reach[g] == 2}
        print(f"  {cls}: de {len(audit)} grupos de control descartados en la ronda 1, "
              f"{len(audit & third)} llegaron a la ronda 3")
        for build in ("melee", "ranged"):
            names = [g for g in reach if gs[g]["build"] == build]
            for k in (1, 2):
                pool = [g for g in names if g in rel[k]]
                ha, hb = rounds.rel(k, cls, "score_a"), rounds.rel(k, cls, "score_b")
                rho = at.spearman([at.geomean(ha[g]) for g in pool], [at.geomean(hb[g]) for g in pool])
                top_a = set(sorted(pool, key=lambda g: -at.geomean(ha[g]))[:10])
                top_b = set(sorted(pool, key=lambda g: -at.geomean(hb[g]))[:10])
                print(f"    {build} ronda {k + 1}: {len(pool)} grupos, Spearman {rho:.2f}, top 10 comparten "
                      f"{len(top_a & top_b)}")
            ordered = sorted(names, key=lambda g: (-reach[g], -at.geomean(rel[reach[g]][g]), g))
            for rank, (g, tier) in enumerate(zip(ordered, at.tiers_for(len(ordered))), 1):
                info = gs[g]
                k = reach[g]
                score = rel[k][g]
                rs = rows_of[(k, g)]
                out_rows.append({
                    "class": cls, "build": build, "shape": info["shape"], "tier": tier, "rank": rank, "group": g,
                    "attacks": " + ".join(attacks[a]["name"] for a in info["attacks"]),
                    "attack_tiers": "".join(attacks[a]["tier"] for a in info["attacks"]),
                    "seeds": ROUNDS[k][0],
                    "score_rel": f"{at.geomean(score):.3f}",
                    "worst_ref": f"{min(score):.3f}", "best_ref": f"{max(score):.3f}",
                    "median_s": f"{st.median(float(r['median_s']) for r in rs):.1f}",
                    "median_kills": f"{st.median(float(r['median_kills']) for r in rs):.1f}",
                    "median_dealt": f"{st.median(float(r['median_dealt']) for r in rs):.0f}",
                })
    with out.open("w", encoding="utf8", newline="") as f:
        f.write(f"# Fase 2 (build/bond_tiers.py): grupos vinculados desde el principio, jugados por las 6 referencias "
                f"de cada clase; tres rondas de {', '.join(str(s) for s, _ in ROUNDS)} semillas por referencia "
                f"(columna seeds). Tier y rank dentro de cada clase y build.\n")
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    if out == TABLE:
        print(f"escrito {TABLE.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 2: tier list de vínculos.")
    parser.add_argument("--sim", action="store_true", help="Correr el simulador antes de escribir la tabla.")
    parser.add_argument("--check", action="store_true", help="Fallar si la tabla no es la que sale de la salida guardada.")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bond_tiers.csv"
            build_table(out)
            if not filecmp.cmp(out, TABLE, shallow=False):
                sys.exit("data/bond_tiers.csv no coincide con simulator/results/fase2/")
        print("bond_tiers.csv coincide con la salida guardada")
        return
    if args.sim:
        run_sim()
    if not all(raw_path(k + 1).exists() for k in range(len(ROUNDS))):
        sys.exit(f"falta la salida de {OUT_DIR.relative_to(ROOT)}: corre con --sim")
    build_table()


if __name__ == "__main__":
    main()
