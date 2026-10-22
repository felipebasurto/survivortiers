"""Por qué cada Pokémon está donde está: cuánto le suma o le resta cada factor a la puntuación de su mejor build.

    python3 build/why.py            # escribe data/species_why.csv
    python3 build/why.py --check    # falla si data/species_why.csv no es lo que dan los datos de hoy

Mínimos cuadrados sobre los 966: log(puntuación de la mejor build, fase 3) frente a ocho factores del juego,
cada uno estandarizado (media 0, desviación 1):

  atk    multiplicador de ataque con el que pega su build: pa o sa según la categoría de sus ataques (media si mezcla)
  group  lo bueno que es su grupo de ataques jugado por un Pokémon cualquiera de su clase (modelo de la fase 3,
         species_builds.Model, que sale de la fase 2)
  hp, df, sd, spd   vida, Defensa, Defensa Especial y velocidad (v3_data.json)
  size   radio de colisión (sprites.js playerRadius, simulator/sim-rs/src/radii.rs)
  types  daño medio que le hacen los disparos enemigos por sus tipos (pokedex_export.json avg_shot_dmg_mult_types)

El efecto de un factor en una especie es exp(peso × valor estandarizado) − 1: cuánto cambia su puntuación frente a
una especie con ese factor en la media. La ficha enseña los dos que más suman y el que más resta. pct es el percentil
del valor entre los 966, de peor a mejor (en size y types, menos es mejor).
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import json
import math
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import attack_tiers as at  # noqa: E402
import bond_tiers as bt  # noqa: E402
import species_builds as sb  # noqa: E402

ROOT = at.ROOT
TABLE = ROOT / "data" / "species_why.csv"
RADII = at.SIM / "sim-rs" / "src" / "radii.rs"
EXPORT = ROOT / "data" / "pokedex_export.json"
FACTORS = ("atk", "group", "hp", "df", "sd", "spd", "size", "types")
LOWER_IS_BETTER = {"size", "types"}


def player_radii() -> dict[int, float]:
    """dex -> radio de colisión del jugador, como radii.rs player_radius (0 = sin dato: el motor usa min(18, r))."""
    text = RADII.read_text(encoding="utf8")
    nums = re.search(r"const PLAYER: \[u16; \d+\] = \[(.*?)\];", text, re.S).group(1)
    return {i: int(v) / 100 for i, v in enumerate(nums.replace("\n", "").split(",")) if v.strip() and int(v)}


def read_table(path: Path) -> list[dict]:
    with path.open(encoding="utf8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def factor_values() -> dict[int, dict[str, float]]:
    v3 = {m["dex"]: m for m in at.load_v3()["dex"]}
    cats = {mid: m["levels"][0]["cat"] for mid, m in at.load_v3()["moves"].items()}
    kinds = {mid: m["kind"] for mid, m in at.load_v3()["moves"].items()}
    export = {p["dex"]: p for p in json.loads(EXPORT.read_text(encoding="utf8"))}
    radii = player_radii()
    phase1 = {r["move_id"]: r for r in bt.attack_rows()}
    rounds = bt.load_rounds()
    models = {cls: sb.Model(cls, rounds, phase1) for cls in at.CLASSES}
    best = {int(r["dex"]): r for r in read_table(sb.RANK_TABLE)}
    builds = {(int(r["dex"]), r["build"]): r for r in read_table(sb.BUILDS_TABLE)}
    out = {}
    for dex, row in best.items():
        mon, group = v3[dex], builds[(dex, row["build"])]["group"]
        attacks = [m for m in group.split("+") if kinds[m] != "buff"]
        phys = sum(cats[m] == "physical" for m in attacks) / len(attacks)
        out[dex] = {
            "score": float(row["median_score"]),
            "atk": phys * mon["pa"] + (1 - phys) * mon["sa"],
            "group": models[at.attacker_class(mon)].predict(group),
            "hp": mon["hp"], "df": mon["df"], "sd": mon["sd"], "spd": mon["spd"],
            "size": radii.get(dex, min(18.0, mon["r"])),
            "types": export[dex]["avg_shot_dmg_mult_types"],
        }
    return out


def fit(values: dict[int, dict[str, float]]) -> tuple[dict[str, float], dict[str, tuple[float, float]], float]:
    """Pesos por factor (sobre el valor estandarizado), media y desviación de cada factor, y R² del ajuste."""
    import numpy as np

    dexes = sorted(values)
    raw = np.array([[_x(values[d], f) for f in FACTORS] for d in dexes])
    mu, sd = raw.mean(0), raw.std(0)
    z = (raw - mu) / sd
    y = np.log([values[d]["score"] for d in dexes])
    a = np.c_[np.ones(len(y)), z]
    w, *_ = np.linalg.lstsq(a, y, rcond=None)
    resid = y - a @ w
    r2 = 1 - float((resid ** 2).sum() / ((y - y.mean()) ** 2).sum())
    return ({f: float(w[i + 1]) for i, f in enumerate(FACTORS)},
            {f: (float(mu[i]), float(sd[i])) for i, f in enumerate(FACTORS)}, r2)


def _x(v: dict[str, float], f: str) -> float:
    """El valor que entra en el ajuste: logaritmo de los multiplicadores y estadísticas; group ya es un logaritmo."""
    return v[f] if f == "group" else math.log(v[f])


def percentile(xs: list[float], x: float, lower_better: bool) -> int:
    """Percentil de x entre xs, 0 el peor y 100 el mejor."""
    below = sum(1 for v in xs if (v > x if lower_better else v < x))
    equal = sum(1 for v in xs if v == x)
    return round(100 * (below + equal / 2) / len(xs))


def rows() -> tuple[list[dict], dict[str, float], float]:
    values = factor_values()
    w, norm, r2 = fit(values)
    cols = {f: [values[d][f] for d in values] for f in FACTORS}
    out = []
    for dex in sorted(values):
        for f in FACTORS:
            mu, sd = norm[f]
            effect = math.exp(w[f] * (_x(values[dex], f) - mu) / sd) - 1
            out.append({"dex": dex, "factor": f, "value": round(values[dex][f], 4),
                        "pct": percentile(cols[f], values[dex][f], f in LOWER_IS_BETTER),
                        "effect": round(effect, 4)})
    return out, w, r2


def write(path: Path) -> None:
    table, w, r2 = rows()
    with path.open("w", encoding="utf8", newline="") as f:
        f.write(f"# build/why.py: efecto de cada factor en la supervivencia de la mejor build (ranking acotado). R² {r2:.3f}. "
                "Pesos: " + ", ".join(f"{k} {v:+.3f}" for k, v in w.items()) + "\n")
        out = csv.DictWriter(f, fieldnames=list(table[0]), lineterminator="\n")
        out.writeheader()
        out.writerows(table)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / TABLE.name
            write(fresh)
            if not filecmp.cmp(fresh, TABLE, shallow=False):
                print(f"{TABLE.relative_to(ROOT)} no coincide con los datos; ejecuta python3 build/why.py", file=sys.stderr)
                return 1
        print(f"{TABLE.name} coincide con los datos")
        return 0
    write(TABLE)
    print(TABLE.read_text(encoding="utf8").splitlines()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
