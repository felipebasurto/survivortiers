"""Selection bias of best_move / best_median_s.  Usage: winners_curse.py solo_sweep.csv [draws=300]

best_median_s is the max of N noisy medians (N = candidate starters). Parametric bootstrap: redraw each
candidate as Normal(median_s, sigma), sigma = (boot_hi-boot_lo)/3.29, and compare. Reports
- flip: share of redraws where a different starter is the max
- optimism: mean(max redraw) - max observed, i.e. how far the published max overshoots the noise-free
  value (a second-order estimate; the first-order bias is of the same size).
"""
import csv
import sys
from collections import defaultdict

import numpy as np

rows = [r for r in csv.DictReader(l for l in open(sys.argv[1], encoding="utf8") if not l.startswith("#"))]
draws = int(sys.argv[2]) if len(sys.argv) > 2 else 300
by = defaultdict(list)
for r in rows:
    by[r["dex"]].append((float(r["median_s"]), (float(r["boot_hi"]) - float(r["boot_lo"])) / 3.29))
rng = np.random.default_rng(7)
out = defaultdict(lambda: ([], [], []))
for c in by.values():
    m = np.array([x[0] for x in c]); s = np.array([x[1] for x in c])
    d = rng.normal(m, s, (draws, len(m)))
    k = 1 if len(m) < 4 else 4 if len(m) < 10 else 10 if len(m) < 20 else 20 if len(m) < 40 else 40
    out[k][0].append(np.mean(d.argmax(axis=1) != m.argmax()))
    out[k][1].append(d.max(axis=1).mean() - m.max())
    out[k][2].append(s.mean())
print(f"species {len(by)}  candidates/species median {np.median([len(c) for c in by.values()]):.0f}")
print("candidates   species  flip-share  mean-redraw-shift(s)  mean-sigma(s)")
for k in sorted(out):
    f, o, s = out[k]
    print(f"  >={k:<3d}      {len(f):5d}     {np.mean(f):.2f}        {np.mean(o):+.2f}              {np.mean(s):.2f}")
