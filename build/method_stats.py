"""Cifras de la página Método, calculadas de los CSV del simulador (simulator/results/fixed_group) y del ranking
publicado (data/ranking_definitive.csv). Nada se escribe a mano: si cambia un CSV, cambia la página.

    stats = compute()

catalog.py lo guarda en meta.json como methodStats. Los números de partidas por fase salen de las constantes de
build/regen.py, que son las que usa el pipeline; test_method_stats.py comprueba que coinciden con las columnas n.
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter
from pathlib import Path

import regen
import tiers

ROOT = Path(__file__).resolve().parent.parent
FIXED = ROOT / "simulator" / "results" / "fixed_group"
RANKING = ROOT / "data" / "ranking_definitive.csv"

START_BINS = (80, 10, 16)  # inicio, ancho en segundos, número de barras: 80 a 240 s
WIDTH_BIN = 25  # ancho de cada barra de márgenes, en puestos
WIDTH_BINS = 14  # 0 a 350 puestos; lo que pase de ahí cae en la última barra
EXAMPLE_RANK = 1  # el Pokémon del puesto 1 explica la nota, con sus medianas de la apertura
DPS_REF = 80.0  # debe ser stats.rs DPS_REF
KPM_REF = 40.0  # debe ser stats.rs KPM_REF


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _stage(name: str, files: list[Path], seeds: int, species_key: str = "dex") -> dict:
    rows = [r for path in files for r in _rows(path)]
    per = Counter(r[species_key] for r in rows)
    hours = sum(float(r["mean_s"]) * seeds for r in rows) / 3600
    return {
        "id": name,
        "rows": len(rows),
        "species": len(per),
        "seeds": seeds,
        "games": len(rows) * seeds,
        "perSpecies": int(statistics.median(per.values())),
        "hours": round(hours),
    }


def _stages() -> list[dict]:
    return [
        _stage("start_screen", [FIXED / "solo_screen.csv"], regen.SCREEN_SEEDS),
        _stage("start_refine", [FIXED / "solo_refine.csv"], regen.SOLO_REFINE_SEEDS),
        _stage("move_duel", [FIXED / "solo_contend.csv"], regen.CONTEND_SEEDS),
        _stage("group_screen", [FIXED / "group_screen.csv"], regen.SCREEN_SEEDS),
        _stage("group_refine", [FIXED / "group_search.csv"], regen.GROUP_REFINE_SEEDS),
        _stage("start_sweep", [FIXED / "g2p2" / "starter_sweep.csv"], regen.START_SEEDS),
        _stage("final", [FIXED / "g2p2" / "rank_200.csv", *(p for p, _ in regen.START_BLOCKS)], regen.START_SEEDS),
    ]


def _histogram(values: list[float], start: float, width: float, bins: int) -> list[int]:
    counts = [0] * bins
    for v in values:
        i = min(max(int((v - start) // width), 0), bins - 1)
        counts[i] += 1
    return counts


def _example(ranking: list[dict]) -> dict:
    """La apertura del Pokémon del puesto 1, con las medianas de su fila en rank_200.csv.
    dps y bajas por minuto salen de esas medianas; la nota es la mediana publicada."""
    top = next(r for r in ranking if int(r["rank"]) == EXAMPLE_RANK)
    row = next(r for r in _rows(FIXED / "g2p2" / "rank_200.csv") if int(r["dex"]) == int(top["dex"]))
    secs = float(row["median_s"])
    dps = float(row["median_dealt"]) / secs
    kpm = float(row["median_kills"]) * 60 / secs
    return {
        "dex": int(top["dex"]),
        "seconds": round(secs),
        "dealt": round(float(row["median_dealt"])),
        "kills": round(float(row["median_kills"])),
        "dps": round(dps),
        "kpm": round(kpm),
        "sDps": round(dps / (dps + DPS_REF), 2),
        "sKpm": round(kpm / (kpm + KPM_REF), 2),
        "score": round(float(row["median_score"])),
    }


def compute() -> dict:
    stages = _stages()
    games = sum(s["games"] for s in stages)
    hours = sum(s["hours"] for s in stages)

    ranking = _rows(RANKING)
    starts = [float(r["start_median_s"]) for r in ranking]
    widths = [int(r["rank_p90"]) - int(r["rank_p10"]) for r in ranking]
    tier_width = {t: round(statistics.median(
        int(r["rank_p90"]) - int(r["rank_p10"]) for r in ranking if r["tier"] == t)) for t, _, _ in tiers.CUTS}

    straddle = []
    for (upper, _, _), (lower, _, _) in zip(tiers.CUTS, tiers.CUTS[1:]):
        edge = tiers.BANDS[upper][1]
        n = sum(1 for r in ranking if int(r["rank_p10"]) <= edge < int(r["rank_p90"]))
        straddle.append({"from": upper, "to": lower, "edge": edge, "count": n})

    any_cross = sum(1 for r in ranking if tiers.TIER_OF[int(r["rank_p10"])] != tiers.TIER_OF[int(r["rank_p90"])])

    start_lo, start_w, start_n = START_BINS
    return {
        "games": games,
        "hours": hours,
        "years": round(hours / 24 / 365),
        "stages": stages,
        "start": {
            "median": round(statistics.median(starts)),
            "min": round(min(starts)),
            "max": round(max(starts)),
            "binStart": start_lo,
            "binWidth": start_w,
            "counts": _histogram(starts, start_lo, start_w, start_n),
        },
        "width": {
            "median": round(statistics.median(widths)),
            "binWidth": WIDTH_BIN,
            "counts": _histogram(widths, 0, WIDTH_BIN, WIDTH_BINS),
        },
        "tierWidth": tier_width,
        "straddle": straddle,
        "straddleAny": any_cross,
        "example": _example(ranking),
    }
