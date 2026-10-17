"""Task list for the per-species counterfactuals behind the ficha summaries (build/summaries.py).

Same protocol as the published rank: --group 2+2 --terrain --status, partners from solo_sweep.csv,
seeds 1-200, so the baseline rows reproduce results/fixed_group/g2p2/rank_200.csv and the best-move
medians bit for bit. Each species runs its game start move and its best sim move (data/ranking_definitive.csv),
once as is and once per stat set to the median of the 966 (v3/v3_data.json): hitbox radius r, speed, HP
and attack. A stat already at the median is skipped. The ranking files are not touched.

    python3 counterfactual_bench.py > /tmp/cf_tasks.txt
    ./sim-rs/target/release/pokesim tasks /tmp/cf_tasks.txt --group 2+2 --terrain --status \
        --partners results/fixed_group/solo_sweep.csv --seeds 200 --out results/fixed_group/counterfactuals_g2p2.csv
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RANKING = ROOT.parent / "data" / "ranking_definitive.csv"
STATS = ("r", "spd", "hp", "atk")


def medians() -> dict[str, float]:
    dex = json.loads((ROOT / "v3" / "v3_data.json").read_text(encoding="utf8"))["dex"]
    return {k: statistics.median(m[k] for m in dex) for k in STATS}


def lines() -> list[str]:
    dex = {m["dex"]: m for m in json.loads((ROOT / "v3" / "v3_data.json").read_text(encoding="utf8"))["dex"]}
    med = medians()
    with RANKING.open(encoding="utf8") as f:
        rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
    out = []
    for r in sorted(rows, key=lambda r: int(r["dex"])):
        d = int(r["dex"])
        moves = [r["start_move"]] + ([r["best_move"]] if r["best_move"] != r["start_move"] else [])
        for mv in moves:
            out.append(f"{d},{mv},none,,,,,,")
            for k in STATS:
                if dex[d][k] != med[k]:
                    out.append(f"{d},{mv},none,,,,,,{k}={med[k]}")
    return out


if __name__ == "__main__":
    print("\n".join(lines()))
