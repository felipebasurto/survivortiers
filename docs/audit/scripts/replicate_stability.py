"""Do independent seed blocks pick the same published group?

Usage (from repo root): [BUILD_DIR=/path/to/other/checkout/build] python3 docs/audit/scripts/replicate_stability.py syn_0.csv ...
BUILD_DIR selects whose combos.py (publish rule) is used; default is this checkout's build/.
Each CSV is `pokesim synergy --seeds 200 --seed0 N --only <file>`, where the file has one `dex|group` line per group (see `parse` in simulator/sim-rs/src/main.rs).
Feeds every block through build/combos.py `_search_picks` (the real publish rule) and compares.
"""
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, os.environ.get("BUILD_DIR", str(ROOT / "build")))
import combos  # noqa: E402

blocks = [Path(p) for p in sys.argv[1:]]
picks = []
for b in blocks:
    combos.SEARCH_CSV = b
    picks.append(combos._search_picks())

dexes = sorted(set().union(*[set(p) for p in picks]))
same_all = 0
for dex in dexes:
    sets = [tuple(sorted(p[dex][0])) + (("harden",) if p[dex][1] else ()) for p in picks if dex in p]
    distinct = {s for s in sets}
    same_all += len(distinct) == 1
    print(f"dex {dex}: {len(distinct)} distinct published groups over {len(sets)} seed blocks")
    for s in sorted(distinct):
        print("   ", sum(x == s for x in sets), "x", "+".join(s))
print(f"species with an identical published group in every block: {same_all}/{len(dexes)}")

times = defaultdict(list)
for b in blocks:
    for r in csv.DictReader(b.open(encoding="utf8")):
        times[(r["dex"], r["group"])].append(float(r["median_s"]))
spread = sorted(max(v) - min(v) for v in times.values() if len(v) == len(blocks))
print(f"same group, different seed block: median range of median_s = {spread[len(spread) // 2]:.1f} s, "
      f"p90 = {spread[int(len(spread) * 0.9)]:.1f} s over {len(spread)} groups")
