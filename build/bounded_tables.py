"""Tablas publicadas desde el ranking acotado (bounded-ranking-v2, run full con naturalezas, 441.486 partidas).

    python3 build/bounded_tables.py

Lee simulator/runpod-ranking/full/candidates.json.gz (extracto de results.json: cada build simulada con sus partidas,
etapas A con 2 semillas, B con 8 y confirmación con 16) y escribe data/species_builds.csv, data/ranking_fase3.csv,
las builds de data/bounded_ranking.json y vacía data/species_variants.csv.

Reglas (Felipe, 22-10-2026):
- Cada build publicada tiene 4 movimientos; las de menos se descartan.
- Sin Placaje, Ataque Rápido ni Golpe Cuerpo, salvo en especies de tipo Normal.
- Por especie, estilo y rama (sin MT / con MT) se elige la build que pasa con la etapa más alta (confirmada, luego B,
  luego A) y, dentro de ella, la mayor mediana de supervivencia. Si ninguna pasa, no hay build (se dice en la ficha).
- El puesto es la mediana de supervivencia de la mejor build sin MT de las dos (cuerpo a cuerpo y distancia); tiers
  con los cortes de data/tiers.json. score_lo y score_hi son el mínimo y el máximo de sus partidas.
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


CAND = ROOT / "simulator/runpod-ranking/full/candidates.json.gz"
BANNED = ("tackle", "quick-attack", "body-slam")
TYPES = {d["dex"]: d["types"] for d in GAME["dex"]}
STAGE_RANK = {"confirmed": 3, "B": 2, "A": 1}
BRANCH = {"optimized_no_tm": "no_tm", "optimized_tm": "optimized"}


def allowed(dex: int, moves: list[str]) -> bool:
    return len(moves) == 4 and ("normal" in TYPES[dex] or not set(BANNED) & set(moves))


def select() -> tuple[dict, list]:
    """(dex, estilo, rama) -> build elegida; y la lista de huecos sin build válida."""
    c = json.loads(gzip.decompress(CAND.read_bytes()))
    best = {}
    for o in c["win"] + [o for o in c["cand"] if o["stage"] in ("A", "B")]:
        if not allowed(o["dex"], o["moves"]):
            continue
        surv = [m[0] for m in o["m"]]
        key = (o["dex"], o["style"], BRANCH[o["branch"]])
        rank = (STAGE_RANK[o["stage"]], statistics.median(surv))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, o)
    gaps = sorted((d["dex"], s, br) for d in GAME["dex"] for s in ("melee", "ranged") for br in ("no_tm", "optimized")
                  if (d["dex"], s, br) not in best)
    return {k: v[1] for k, v in best.items()}, gaps


def _start(o: dict) -> list[str]:
    g = o["group"]
    return [g[0]] + ([o["secondStart"]] if o["secondStart"] and o["secondStart"] != g[0] else [])


def _metrics(o: dict) -> dict:
    ms = o["m"]
    return {"survival": round(statistics.median(m[0] for m in ms), 1),
            "kpm": round(statistics.fmean(m[1] * 60 / m[0] for m in ms), 2),
            "dps": round(statistics.fmean(m[2] / m[0] for m in ms), 1),
            "kills": round(statistics.fmean(m[1] for m in ms), 1), "seeds": len(ms), "stage": o["stage"]}


def write_bounded(sel: dict, gaps: list) -> None:
    path = ROOT / "data/bounded_ranking.json"
    doc = json.loads(path.read_text(encoding="utf8"))
    species = {str(d["dex"]): {} for d in GAME["dex"]}
    wins = {"melee": {}, "ranged": {}}
    for (dex, style, br), o in sorted(sel.items()):
        species[str(dex)][f"{style}|{br}"] = dict(
            attacks=o["moves"], start=_start(o), ability=o["ability"], nature=o["nature"], tms=o["tms"], **_metrics(o))
        wins[style][o["nature"]] = wins[style].get(o["nature"], 0) + 1
    doc["species"] = species
    doc["natureWins"] = wins
    doc["selection"] = {"rules": "4 movimientos; sin " + ", ".join(BANNED) + " salvo tipo Normal; etapa más alta, "
                        "luego mediana de supervivencia", "source": "simulator/runpod-ranking/full/candidates.json.gz",
                        "gaps": [list(g) for g in gaps]}
    doc["source"]["rows"] = len(sel)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf8")


def main() -> None:
    sel, gaps = select()
    write_bounded(sel, gaps)
    out = []
    for (dex, style, br), o in sorted(sel.items()):
        if br != "no_tm":
            continue
        ids = o["moves"]
        start = _start(o)
        attacks = [m for m in start if _kind(m) != "buff"] + [m for m in ids if m not in start and _kind(m) != "buff"]
        buffs = [m for m in ids if _kind(m) == "buff"]
        group = attacks + buffs
        cats = {_cat(m) for m in attacks}
        surv = sorted(m[0] for m in o["m"])
        med = round(statistics.median(surv), 3)
        out.append({
            "dex": dex, "name": NAMES[dex], "build": style, "group": "+".join(group),
            "attacks": " + ".join(MOVES[m]["levels"][0]["name"] for m in attacks),
            "boosts": " + ".join(MOVES[m]["levels"][0]["name"] for m in buffs),
            "mix": cats.pop() if len(cats) == 1 else "mixed" if cats else "none", "seeds": len(surv),
            "median_s": med, "median_kills": round(statistics.median(m[1] for m in o["m"]), 3),
            "median_dealt": round(statistics.median(m[2] for m in o["m"]), 3),
            "median_score": med, "score_lo": round(surv[0], 3), "score_hi": round(surv[-1], 3),
        })
    out.sort(key=lambda r: (r["dex"], r["build"]))
    dexes = {d["dex"] for d in GAME["dex"]}
    have = {(r["dex"], r["build"]) for r in out}
    missing = sorted((d, s) for d in dexes for s in ("melee", "ranged") if (d, s) not in have)
    gp = ROOT / "data/bounded_gaps.csv"
    gp.write_text("# Especie, estilo y rama sin build simulada de 4 movimientos que cumpla las reglas (build/bounded_tables.py).\n"
                  "dex,name,build,branch\n" + "".join(f"{d},{NAMES[d]},{st},{br}\n" for d, st, br in gaps), encoding="utf8")
    print(f"huecos: {len(gaps)} (data/bounded_gaps.csv)")
    if any(d not in {r["dex"] for r in out} for d in dexes):
        raise SystemExit(f"especies sin ninguna build sin MT válida: {missing}")
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
             "median_s": r["median_s"], "other_build": other[r["dex"]]["build"] if r["dex"] in other else "",
             "other_score": other[r["dex"]]["median_score"] if r["dex"] in other else ""} for i, r in enumerate(ranked, 1)]
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
