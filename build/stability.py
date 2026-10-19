#!/usr/bin/env python3
"""How stable the top of the ranking is across seeds.

Every row of the merged solo sweep carries the median score of the first half of its seeds
(`score_a`) and of the second half (`score_b`, `simulator/sim-rs/src/stats.rs`). Each half
ranks the 966 species on their best attacking move, with the owner's rules (build/picks.py).
The report is the overlap of the two top-N lists (Jaccard) and the published top N against
each half. A row run on 16 seeds has 8 per half; a contender refreshed on 512 seeds has 256.

    python3 build/stability.py                 # top 30, simulator/results/fixed_group/solo_sweep.csv
    python3 build/stability.py --top 30 --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import picks

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "simulator" / "results" / "fixed_group" / "solo_sweep.csv"
RANKING = ROOT / "data" / "ranking_definitive.csv"


def best_by_half(rows: list[dict], key: str) -> dict[int, float]:
    """dex -> best adjusted score of an attacking move, measured on one half of the seeds."""
    best: dict[int, float] = {}
    for row in rows:
        dex = int(row["dex"])
        if not picks.move_ok(dex, row) or row.get(key) in (None, ""):
            continue
        value = picks.owner_rules.adjusted(float(row[key]), row.get("kind") == "melee")
        best[dex] = max(best.get(dex, 0.0), value)
    return best


def top(scores: dict[int, float], n: int) -> set[int]:
    return set(sorted(scores, key=lambda d: (-scores[d], d))[:n])


def jaccard(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def published_top(n: int) -> set[int]:
    rows = picks.load_rows(RANKING)
    return {int(r["dex"]) for r in rows if int(r["rank"]) <= n}


def report(sweep: Path, n: int) -> dict:
    rows = picks.load_rows(sweep)
    seeds = sorted({int(r["n"]) for r in rows if r.get("n")})
    a, b = top(best_by_half(rows, "score_a"), n), top(best_by_half(rows, "score_b"), n)
    out = {"top": n, "seeds_per_row": seeds[:1] + seeds[-1:], "half_a_vs_half_b": round(jaccard(a, b), 3)}
    if RANKING.exists():
        pub = published_top(n)
        out["published_vs_half_a"] = round(jaccard(pub, a), 3)
        out["published_vs_half_b"] = round(jaccard(pub, b), 3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", type=Path, default=SWEEP)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = report(args.sweep, args.top)
    if args.json:
        print(json.dumps(result))
        return
    lo, hi = result["seeds_per_row"][0], result["seeds_per_row"][-1]
    print(f"top {args.top}: split-half overlap {result['half_a_vs_half_b']:.3f} (seeds per row {lo} to {hi})")
    for k in ("published_vs_half_a", "published_vs_half_b"):
        if k in result:
            print(f"  {k.replace('_', ' ')}: {result[k]:.3f}")


if __name__ == "__main__":
    main()
