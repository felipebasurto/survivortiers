"""Re-draw the sim inputs of the published ranking with measured seed noise and see how far ranks move.

Usage: rank_noise_inject.py data/ranking_definitive.csv [sigma_seconds=2.0] [draws=200]

sigma 2.0 s is the per-group seed-block noise of median_s measured by replicate_stability.py
(median range 4.2 s across 4 blocks of 200 seeds => sigma ~2). Only the sim columns (start_median_s,
best_median_s) move; the sheet and v4 ranks stay frozen, exactly as make_definitive.py treats them.
Tier gates (stat/type caps) are ignored, so tier moves are from rank cuts 30/120/320/620 only.
"""
import csv
import sys

import numpy as np

path = sys.argv[1]
sigma = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
draws = int(sys.argv[3]) if len(sys.argv) > 3 else 200
rows = list(csv.DictReader(l for l in open(path, encoding="utf8") if not l.startswith("#")))
rows.sort(key=lambda r: int(r["dex"]))
N = len(rows)
col = lambda k: np.array([float(r[k]) for r in rows])
sheet, v4m, v4f, start, best = col("rank_sheet"), col("rank_v4_max"), col("rank_v4_fresh"), col("start_median_s"), col("best_median_s")
pub_rank = col("rank")


def ranks_of(score):
    order = np.argsort(-score, kind="stable")
    r = np.empty(N)
    r[order] = np.arange(1, N + 1)
    return r


pct = lambda r: (N - r + 0.5) / N


def final(start_s, best_s):
    early = ranks_of(np.exp((10 * np.log(pct(ranks_of(start_s))) + 45 * np.log(pct(ranks_of(best_s)))) / 55))
    late = ranks_of(np.exp(2 / 3 * np.log(pct(v4m)) + 1 / 3 * np.log(pct(v4f))))
    return ranks_of(np.exp((45 * np.log(pct(sheet)) + 30 * np.log(pct(early)) + 25 * np.log(pct(late))) / 100))


base = final(start, best)
print(f"baseline reproduces published rank exactly for {int((base == pub_rank).sum())}/{N}; "
      f"median |diff| {np.median(np.abs(base - pub_rank)):.0f} (tier gates and stored v4 weights account for the rest)")
rng = np.random.default_rng(1)
cuts = np.array([30, 120, 320, 620])
band = lambda r: np.searchsorted(cuts, r - 0.5)
shift = []
bandmove = []
for _ in range(draws):
    r = final(start + rng.normal(0, sigma, N), best + rng.normal(0, sigma, N))
    shift.append(np.abs(r - base))
    bandmove.append(band(r) != band(base))
shift = np.array(shift)
print(f"sigma {sigma}s on start+best median: mean |rank shift| {shift.mean():.1f}, p90 {np.percentile(shift, 90):.0f}, "
      f"share of species that change tier band in a typical draw {np.mean(bandmove):.2f}")
top = base <= 30
print(f"top-30: mean |shift| {shift[:, top].mean():.1f}; share of S slots that change membership per draw "
      f"{np.mean([(final_top != top).sum() / 2 / 30 for final_top in [(final(start + rng.normal(0, sigma, N), best + rng.normal(0, sigma, N)) <= 30) for _ in range(50)]]):.2f}")
