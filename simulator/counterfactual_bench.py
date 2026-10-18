"""Task list for the per-species counterfactuals behind the ficha summaries (build/summaries.py).

Same protocol as the published rank: --group 2+2 --terrain --status, partners from solo_sweep.csv,
seeds 1-200, so the baseline rows reproduce results/fixed_group/g2p2/rank_200.csv and the best-move
medians bit for bit. Each species runs its game start move and its best sim move (data/ranking_definitive.csv),
once as is and once per stat set to the median of the 966 (v3/v3_data.json): hitbox radius r, speed, HP
and attack. A stat already at the median is skipped. The ranking files are not touched.

    python3 counterfactual_bench.py > /tmp/cf_tasks.txt
    ./sim-rs/target/release/pokesim tasks /tmp/cf_tasks.txt --group 2+2 --terrain --status \
        --partners results/fixed_group/solo_sweep.csv --seeds 200 --out results/fixed_group/counterfactuals_g2p2.csv

    # best move only, matching the solo sweep (no group, extra kinds on):
    python3 counterfactual_bench.py --solo-best > /tmp/cf_solo.txt
    ./sim-rs/target/release/pokesim tasks /tmp/cf_solo.txt --terrain --status --xkinds --seeds 200 \
        --out results/fixed_group/counterfactuals_solo.csv
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RANKING = ROOT.parent / "data" / "ranking_definitive.csv"
STATS = ("r", "spd", "hp", "atk")


def medians() -> dict[str, float]:
    dex = json.loads((ROOT / "v3" / "v3_data.json").read_text(encoding="utf8"))["dex"]
    return {k: statistics.median(m[k] for m in dex) for k in STATS}


def _rows() -> list[dict]:
    with RANKING.open(encoding="utf8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def _emit(rows: list[dict], moves_of) -> list[str]:
    dex = {m["dex"]: m for m in json.loads((ROOT / "v3" / "v3_data.json").read_text(encoding="utf8"))["dex"]}
    med = medians()
    out = []
    for r in sorted(rows, key=lambda r: int(r["dex"])):
        d = int(r["dex"])
        for mv in moves_of(r):
            out.append(f"{d},{mv},none,,,,,,")
            for k in STATS:
                if dex[d][k] != med[k]:
                    out.append(f"{d},{mv},none,,,,,,{k}={med[k]}")
    return out


def lines() -> list[str]:
    def moves_of(r: dict) -> list[str]:
        moves = [r["start_move"]]
        if r["best_move"] != r["start_move"]:
            moves.append(r["best_move"])
        return moves

    return _emit(_rows(), moves_of)


def solo_best_lines() -> list[str]:
    """Best-move rows only, for the solo sweep protocol (no group)."""
    return _emit(_rows(), lambda r: [r["best_move"]])


if __name__ == "__main__":
    chosen = solo_best_lines() if "--solo-best" in sys.argv[1:] else lines()
    print("\n".join(chosen))
