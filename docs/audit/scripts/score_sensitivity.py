"""How much does the choice of score decide the "best move"?  Usage: score_sensitivity.py solo_sweep.csv

Reads a solo_sweep.csv that has the #35 score columns (median_dealt, median_score, mean_score,
score_lo, score_hi) and prints, per species winner, how the answer moves with the formula.
"""
import csv
import statistics as st
import sys
from collections import Counter, defaultdict

path = sys.argv[1]
rows = [r for r in csv.DictReader(l for l in open(path, encoding="utf8") if not l.startswith("#"))]
if "median_score" not in rows[0]:
    sys.exit("no score columns in this sweep (pre-#35)")

by = defaultdict(list)
for r in rows:
    for k in ("median_s", "mean_s", "boot_lo", "boot_hi", "median_dealt", "median_score", "mean_score",
              "score_lo", "score_hi", "median_kills"):
        r[k] = float(r[k])
    by[r["dex"]].append(r)

formulas = {
    "time (median_s)": lambda r: r["median_s"],
    "time x dealt x (1+kills) median (#35)": lambda r: r["median_score"],
    "time x dealt x (1+kills) mean": lambda r: r["mean_score"],
    "time x dealt": lambda r: r["median_s"] * r["median_dealt"],
    "time x sqrt(dealt x (1+kills))": lambda r: r["median_s"] * (r["median_dealt"] * (1 + r["median_kills"])) ** 0.5,
    "dealt": lambda r: r["median_dealt"],
}
win = {}
for name, f in formulas.items():
    win[name] = {d: max(rs, key=f) for d, rs in by.items()}
print(f"species {len(by)}  rows {len(rows)}")
base = win["time (median_s)"]
for name, w in win.items():
    c = Counter(x["start"] for x in w.values())
    diff = sum(w[d]["start"] != base[d]["start"] for d in w)
    print(f"{name:42s} winner==time-winner in {len(w) - diff:4d}/{len(w)}  substitute wins {c['substitute']:4d}  top3 {c.most_common(3)}")

rel_t = [(r["boot_hi"] - r["boot_lo"]) / r["median_s"] for r in rows if r["median_s"]]
rel_s = [(r["score_hi"] - r["score_lo"]) / r["median_score"] for r in rows if r["median_score"]]
print(f"median relative 90% bootstrap width: time {st.median(rel_t):.3f}  score {st.median(rel_s):.3f}")


def margin(key):
    out = []
    for rs in by.values():
        v = sorted((r[key] for r in rs), reverse=True)
        if len(v) > 1 and v[1] > 0:
            out.append(v[0] / v[1] - 1)
    return st.median(out)


print(f"median best-vs-second margin: time {margin('median_s'):.3f}  score {margin('median_score'):.3f}")


def disjoint(lo, hi, key):
    n = 0
    for rs in by.values():
        rs = sorted(rs, key=lambda r: -r[key])
        if len(rs) > 1 and rs[0][lo] > rs[1][hi]:
            n += 1
    return n


print(f"winner interval disjoint from runner-up: time {disjoint('boot_lo', 'boot_hi', 'median_s')}  "
      f"score {disjoint('score_lo', 'score_hi', 'median_score')}")
sub = [r for r in rows if r["start"] == "substitute"]
oth = [r for r in rows if r["start"] != "substitute"]
print(f"substitute: median_s {st.median(r['median_s'] for r in sub):.1f} vs rest {st.median(r['median_s'] for r in oth):.1f}; "
      f"median_dealt {st.median(r['median_dealt'] for r in sub):.0f} vs {st.median(r['median_dealt'] for r in oth):.0f}; "
      f"median_kills {st.median(r['median_kills'] for r in sub):.0f} vs {st.median(r['median_kills'] for r in oth):.0f}")
