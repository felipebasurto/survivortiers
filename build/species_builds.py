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

Ranking: median_score de la ronda C (supervivencia, daño y bajas; simulator/sim-rs/src/stats.rs) de la mejor de las
dos builds. Tiers con los cortes de data/tiers.json.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import hashlib
import math
import statistics as st
import sys
import tempfile
from pathlib import Path

import attack_tiers as at
import bond_tiers as bt
import builds
import picks
import tiers

ROOT = at.ROOT
SIM = at.SIM
OUT_DIR = SIM / "results" / "fase3"
BUILDS_TABLE = ROOT / "data" / "species_builds.csv"
RANK_TABLE = ROOT / "data" / "ranking_fase3.csv"

SECONDS = "900"
TOP_A = 30  # por especie, build y mezcla de categorías
TOP_B = 4  # por especie y build
ROUNDS = ((4, 0), (32, 100), (128, 1000))  # (semillas, seed0) de las rondas A, B y C
MIXES = ("physical", "special", "mixed")


def only_path(k: int) -> Path:
    return OUT_DIR / f"r{'ABC'[k]}_only.txt"


def raw_path(k: int) -> Path:
    return OUT_DIR / f"r{'ABC'[k]}_raw.csv"


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


def shortlist() -> dict[tuple[int, str], list[str]]:
    """(dex, build) -> grupos de la ronda A."""
    phase1 = {r["move_id"]: r for r in bt.attack_rows()}
    rounds = bt.load_rounds()
    models = {cls: Model(cls, rounds, phase1) for cls in at.CLASSES}
    out: dict[tuple[int, str], list[str]] = {}
    for mon in at.load_v3()["dex"]:
        model = models[at.attacker_class(mon)]
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
    h = hashlib.sha256(repr((ROUNDS[k], SECONDS)).encode())
    for path in sorted((SIM / "sim-rs" / "src").rglob("*")) + [SIM / "v3" / "v3_data.json"]:
        if path.is_file():
            h.update(str(path.relative_to(SIM)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def run_round(k: int, keys: dict[tuple[int, str], list[str]]) -> None:
    """Simula los grupos de la ronda k que faltan. Un grupo con el mismo motor, datos y semillas da la misma fila,
    así que las filas guardadas con la misma huella se reutilizan; si la huella cambia, la ronda se hace entera."""
    seeds, seed0 = ROUNDS[k]
    need = {(dex, g) for (dex, _), gs in keys.items() for g in gs}
    stamp = raw_path(k).with_suffix(".fingerprint")
    have: dict[tuple[int, str], dict] = {}
    if raw_path(k).exists() and stamp.exists() and stamp.read_text().strip() == fingerprint(k):
        have = {key: r for key, r in load(raw_path(k)).items() if key in need}
    todo = sorted(need - set(have))
    print(f"ronda {'ABC'[k]}: {len(need)} grupos, {len(have)} ya jugados, {len(todo)} x {seeds} semillas = "
          f"{len(todo) * seeds} partidas", flush=True)
    if todo:
        only_path(k).write_text("".join(f"{dex}|{g}\n" for dex, g in todo), encoding="utf8")
        fresh = OUT_DIR / f"r{'ABC'[k]}_new.csv"
        bt.synergy(only_path(k), fresh, seeds, seed0)
        have.update(load(fresh))
        fresh.unlink()
    with raw_path(k).open("w", encoding="utf8", newline="") as f:
        rows = [have[key] for key in sorted(need)]
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    stamp.write_text(fingerprint(k) + "\n", encoding="utf8")


def run_sim() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keys = shortlist()
    for k in range(len(ROUNDS)):
        run_round(k, keys)
        if k + 1 < len(ROUNDS):
            keys = advance(load(raw_path(k)), keys, TOP_B if k == 0 else 1)


def build_tables(builds_out: Path = BUILDS_TABLE, rank_out: Path = RANK_TABLE) -> None:
    v3 = {m["dex"]: m for m in at.load_v3()["dex"]}
    names = builds._game_moves()
    rows = [load(raw_path(k)) for k in range(len(ROUNDS))]
    keys_a: dict[tuple[int, str], list[str]] = {}
    for (dex, g) in rows[0]:
        keys_a.setdefault((dex, builds._kind(picks.split_group(g)[0])), []).append(g)
    keys_b = advance(rows[0], keys_a, TOP_B)
    keys_c = advance(rows[1], keys_b, 1)

    out_rows = []
    for (dex, build), (g,) in sorted(keys_c.items()):
        r = rows[2][(dex, g)]
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
                f"desde el principio; cifras de {ROUNDS[2][0]} semillas que no se usaron para elegirla.\n")
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
    halves = {d: (float(rows[2][(d, r["group"])]["score_a"]), float(rows[2][(d, r["group"])]["score_b"]))
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
    parser.add_argument("--check", action="store_true", help="Fallar si las tablas no son las que sale de la salida guardada.")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            b, r = Path(tmp) / "b.csv", Path(tmp) / "r.csv"
            build_tables(b, r)
            if not (filecmp.cmp(b, BUILDS_TABLE, shallow=False) and filecmp.cmp(r, RANK_TABLE, shallow=False)):
                sys.exit("species_builds.csv o ranking_fase3.csv no coinciden con simulator/results/fase3/")
        print("species_builds.csv y ranking_fase3.csv coinciden con la salida guardada")
        return
    if args.sim:
        run_sim()
    if not all(raw_path(k).exists() for k in range(len(ROUNDS))):
        sys.exit(f"falta la salida de {OUT_DIR.relative_to(ROOT)}: corre con --sim")
    build_tables()


if __name__ == "__main__":
    main()
