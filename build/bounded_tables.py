"""Tablas publicadas desde el ranking acotado (bounded-ranking-v2, run full con naturalezas, 441.486 partidas).

    python3 build/bounded_tables.py

Lee simulator/runpod-ranking/full/sim-results.json(.gz) y escribe data/species_builds.csv, data/ranking_fase3.csv
(mismo formato que antes, el nombre se mantiene por compatibilidad) y vacía data/species_variants.csv.

Métrica: supervivencia media (s) de la mejor build confirmada sin MT de cada estilo, en las 16 partidas de
confirmación. El ranking toma la mejor de las dos (cuerpo a cuerpo y distancia), como hacía la fase 3, y los tiers salen
del puesto con los mismos cortes de data/tiers.json. Las builds con MT se enseñan aparte en la ficha: no todas las
especies tienen una, así que no entran en el orden. score_lo y score_hi son el mínimo y el máximo de la
supervivencia en esas 16 partidas.
"""
from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import tiers  # noqa: E402

SRC = ROOT / "simulator/runpod-ranking/full/sim-results.json"
GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
MOVES = GAME["moves"]
NAMES = {d["dex"]: d["name"] for d in GAME["dex"]}
HEAD_B = ("# Ranking acotado (build/bounded_tables.py, bounded-ranking-v2): la mejor build sin MT de cada especie y "
          "estilo; supervivencia media de 16 partidas de confirmación (median_s y median_score), mínimo-máximo de las 16 en score_lo/hi.\n")
HEAD_R = ("# Ranking acotado (build/bounded_tables.py): puesto por la supervivencia media de la mejor build sin MT de "
          "cada especie. Tiers de data/tiers.json.\n")


def _load() -> dict:
    gz = SRC.with_suffix(".json.gz")
    raw = SRC.read_bytes() if SRC.exists() else gzip.decompress(gz.read_bytes())
    return json.loads(raw)


def _kind(mid: str) -> str:
    return MOVES[mid]["kind"]


def _cat(mid: str) -> str:
    return MOVES[mid]["levels"][0]["cat"]


def main() -> None:
    doc = _load()
    out = []
    for r in doc["results"]:
        b = r["build"]
        if b["availability"] != "no_tm":
            continue
        ids = [a["id"] for a in sorted(b["attacks"], key=lambda a: a["position"])]
        start = b["initial_attacks"]
        attacks = [m for m in start if _kind(m) != "buff"] + [m for m in ids if m not in start and _kind(m) != "buff"]
        buffs = [m for m in ids if _kind(m) == "buff"]
        group = attacks + buffs
        cats = {_cat(m) for m in attacks}
        matches = r["paired_confirmation"]["candidateMatches"]
        surv = sorted(m["survivalSeconds"] for m in matches)
        met = r["score"]["metrics"]
        out.append({
            "dex": r["pokemon"]["dex"], "name": NAMES[r["pokemon"]["dex"]], "build": b["style"], "group": "+".join(group),
            "attacks": " + ".join(MOVES[m]["levels"][0]["name"] for m in attacks),
            "boosts": " + ".join(MOVES[m]["levels"][0]["name"] for m in buffs),
            "mix": cats.pop() if len(cats) == 1 else "mixed", "seeds": len(matches),
            "median_s": round(met["survivalSeconds"], 3), "median_kills": round(met["meanKills"], 3),
            "median_dealt": round(statistics.fmean(m["damage"] for m in matches), 3),
            "median_score": round(met["survivalSeconds"], 3), "score_lo": round(surv[0], 3), "score_hi": round(surv[-1], 3),
        })
    out.sort(key=lambda r: (r["dex"], r["build"]))
    dexes = {d["dex"] for d in GAME["dex"]}
    have = {(r["dex"], r["build"]) for r in out}
    missing = sorted((d, s) for d in dexes for s in ("melee", "ranged") if (d, s) not in have)
    if missing:
        raise SystemExit(f"faltan filas del ranking acotado: {missing}")
    with (ROOT / "data/species_builds.csv").open("w", encoding="utf8", newline="") as f:
        f.write(HEAD_B)
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    best, other = {}, {}
    for row in out:
        cur = best.get(row["dex"])
        if cur is None or row["median_score"] > cur["median_score"]:
            if cur is not None:
                other[row["dex"]] = cur
            best[row["dex"]] = row
        else:
            other[row["dex"]] = row
    ranked = sorted(best.values(), key=lambda r: (-r["median_score"], r["dex"]))
    rows = [{"rank": i, "dex": r["dex"], "name": r["name"], "tier": tiers.TIER_OF[i], "build": r["build"],
             "group": r["group"], "median_score": r["median_score"], "score_lo": r["score_lo"], "score_hi": r["score_hi"],
             "median_s": r["median_s"], "other_build": other[r["dex"]]["build"],
             "other_score": other[r["dex"]]["median_score"]} for i, r in enumerate(ranked, 1)]
    with (ROOT / "data/ranking_fase3.csv").open("w", encoding="utf8", newline="") as f:
        f.write(HEAD_R)
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    vpath = ROOT / "data/species_variants.csv"
    lines = vpath.read_text(encoding="utf8").splitlines()
    vpath.write_text("# Variantes: no hay en el ranking acotado (una build por estilo).\n" + lines[1] + "\n", encoding="utf8")
    for r in rows[:10]:
        print(r["rank"], r["dex"], r["name"], r["tier"], r["build"], r["median_score"], r["group"])


if __name__ == "__main__":
    main()
