"""How wide is the published rank uncertainty?  Usage: rank_noise.py data/ranking_definitive.csv"""
import csv
import statistics as st
import sys
from collections import Counter

rows = list(csv.DictReader(l for l in open(sys.argv[1], encoding="utf8") if not l.startswith("#")))
w = [float(r["rank_p90"]) - float(r["rank_p10"]) for r in rows]
print(f"species {len(rows)}  tiers {dict(Counter(r['tier'] for r in rows))}")
print(f"rank_p10..p90 width: median {st.median(w):.0f}  p90 {sorted(w)[int(len(w) * .9)]:.0f}  max {max(w):.0f}")
for t in "SABCD":
    ps = [float(r["p_tier"]) for r in rows if r["tier"] == t]
    if ps:
        print(f"tier {t}: n={len(ps)}  median p_tier={st.median(ps):.2f}  share with p_tier<0.8: {sum(p < .8 for p in ps) / len(ps):.2f}")
print("sim spread of the three components is NOT in these intervals: only the 2000-draw jitter inside each "
      "bootstrap CI of start/best medians (make_definitive.py draw()).")
