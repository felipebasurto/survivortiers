"""Tablas publicadas desde el ranking acotado.

    python3 build/bounded_tables.py

Lee simulator/runpod-ranking/full/candidates.json.gz (cada build simulada con sus partidas: etapa A con 2, B con 8 y
confirmada con 16) y escribe data/species_builds.csv, data/ranking_fase3.csv, las builds de data/bounded_ranking.json
y vacía data/species_variants.csv.

Reglas (Felipe, 22-10-2026):
- El puesto es la mediana de supervivencia de la build confirmada (16 partidas) sin MT, la mejor de los dos estilos.
  Las de 2 y 8 partidas no cuentan para el orden. Tiers con los cortes de data/tiers.json.
- Builds de la ficha, por estilo y rama (sin MT / con MT): 4 movimientos, con Danza Espada o Maquinación (o Fortaleza
  si rinde más), sin Placaje, Ataque Rápido ni Golpe Cuerpo salvo tipo Normal. Etapa más alta primero (confirmada, B,
  A) y luego mayor mediana. Si ninguna cumple, la mejor de 4 movimientos sin vetados y, si tampoco, la mejor sin más.
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

GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
MOVES = GAME["moves"]
NAMES = {d["dex"]: d["name"] for d in GAME["dex"]}
HEAD_B = ("# Ranking acotado (build/bounded_tables.py): la build confirmada sin MT de cada especie y estilo; mediana de "
          "supervivencia de sus 16 partidas (median_s y median_score), mínimo-máximo en score_lo/hi.\n")
HEAD_R = ("# Ranking acotado (build/bounded_tables.py): puesto por la mediana de supervivencia de la mejor build "
          "confirmada sin MT de cada especie. Tiers de data/tiers.json.\n")
CAND = ROOT / "simulator/runpod-ranking/full/candidates.json.gz"
BANNED = ("tackle", "quick-attack", "body-slam")
SETUP = ("swords-dance", "nasty-plot", "harden")
TYPES = {d["dex"]: d["types"] for d in GAME["dex"]}
STAGE_RANK = {"confirmed": 3, "B": 2, "A": 1}
BRANCH = {"optimized_no_tm": "no_tm", "optimized_tm": "optimized"}


def _kind(mid: str) -> str:
    return MOVES[mid]["kind"]


def _cat(mid: str) -> str:
    return MOVES[mid]["levels"][0]["cat"]


def allowed(dex: int, moves: list[str]) -> bool:
    return len(moves) == 4 and ("normal" in TYPES[dex] or not set(BANNED) & set(moves))


def preferred(dex: int, moves: list[str]) -> bool:
    return allowed(dex, moves) and bool(set(SETUP) & set(moves))


def _median(o: dict) -> float:
    return statistics.median(m[0] for m in o["m"])


def select(c: dict) -> dict:
    """(dex, estilo, rama) -> build de la ficha."""
    best = {}
    for o in c["win"] + [o for o in c["cand"] if o["stage"] in ("A", "B")]:
        key = (o["dex"], o["style"], BRANCH[o["branch"]])
        rank = (preferred(o["dex"], o["moves"]), allowed(o["dex"], o["moves"]), STAGE_RANK[o["stage"]], _median(o))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, o)
    return {k: v[1] for k, v in best.items()}


def confirmed_no_tm(c: dict) -> dict:
    """(dex, estilo) -> build confirmada sin MT."""
    return {(o["dex"], o["style"]): o for o in c["win"] if o["branch"] == "optimized_no_tm"}


def _start(o: dict) -> list[str]:
    g = o["group"]
    return [g[0]] + ([o["secondStart"]] if o["secondStart"] and o["secondStart"] != g[0] else [])


def _metrics(o: dict) -> dict:
    ms = o["m"]
    return {"survival": round(_median(o), 1),
            "kpm": round(statistics.fmean(m[1] * 60 / m[0] for m in ms), 2),
            "dps": round(statistics.fmean(m[2] / m[0] for m in ms), 1),
            "kills": round(statistics.fmean(m[1] for m in ms), 1), "seeds": len(ms), "stage": o["stage"]}


def write_bounded(sel: dict) -> None:
    path = ROOT / "data/bounded_ranking.json"
    doc = json.loads(path.read_text(encoding="utf8"))
    species = {str(d["dex"]): {} for d in GAME["dex"]}
    wins = {"melee": {}, "ranged": {}}
    for (dex, style, br), o in sorted(sel.items()):
        species[str(dex)][f"{style}|{br}"] = dict(
            attacks=o["moves"], start=_start(o), ability=o["ability"], nature=o["nature"], tms=o["tms"],
            rules=preferred(dex, o["moves"]), **_metrics(o))
        wins[style][o["nature"]] = wins[style].get(o["nature"], 0) + 1
    doc["species"] = species
    doc["natureWins"] = wins
    doc["selection"] = {"rules": "4 movimientos con " + ", ".join(SETUP) + "; sin " + ", ".join(BANNED) +
                        " salvo tipo Normal; etapa más alta, luego mediana de supervivencia; si ninguna cumple, la mejor",
                        "source": "simulator/runpod-ranking/full/candidates.json.gz"}
    doc["source"]["rows"] = len(sel)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf8")


def main() -> None:
    c = json.loads(gzip.decompress(CAND.read_bytes()))
    write_bounded(select(c))
    out = []
    for (dex, style), o in sorted(confirmed_no_tm(c).items()):
        ids = o["moves"]
        start = _start(o)
        attacks = [m for m in start if _kind(m) != "buff"] + [m for m in ids if m not in start and _kind(m) != "buff"]
        buffs = [m for m in ids if _kind(m) == "buff"]
        cats = {_cat(m) for m in attacks}
        surv = sorted(m[0] for m in o["m"])
        med = round(statistics.median(surv), 3)
        out.append({
            "dex": dex, "name": NAMES[dex], "build": style, "group": "+".join(attacks + buffs),
            "attacks": " + ".join(MOVES[m]["levels"][0]["name"] for m in attacks),
            "boosts": " + ".join(MOVES[m]["levels"][0]["name"] for m in buffs),
            "mix": cats.pop() if len(cats) == 1 else "mixed" if cats else "none", "seeds": len(surv),
            "median_s": med, "median_kills": round(statistics.median(m[1] for m in o["m"]), 3),
            "median_dealt": round(statistics.median(m[2] for m in o["m"]), 3),
            "median_score": med, "score_lo": round(surv[0], 3), "score_hi": round(surv[-1], 3),
        })
    missing = sorted({d["dex"] for d in GAME["dex"]} - {r["dex"] for r in out})
    if missing:
        raise SystemExit(f"especies sin build confirmada sin MT: {missing}")
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
    print("Pawmi:", next(r["rank"] for r in rows if r["name"] == "Pawmi"))


if __name__ == "__main__":
    main()
