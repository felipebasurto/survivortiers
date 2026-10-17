"""Summarise the passive benchmark CSVs. Prints lifts the site copy is written from.

Lift is the median, across species, of (this setup − baseline) / baseline. That is the
same aggregation as the item page (Leftovers +28 %, Shell Bell +36 %).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
MECH = ROOT.parent / "data" / "move_mechanics.json"
NAMES = {
    "": "base",
    "0": "atk",
    "1": "spd",
    "2": "hp",
    "3": "def",
    "4": "cd",
    "5": "rgn",
    "6": "mag",
    "7": "xp",
    "8": "heal",
}


def load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def fnum(row: dict, key: str) -> float:
    return float(row[key])


def key_of(row: dict) -> tuple:
    return (row["item"], row["fill"], row.get("stop", ""), row.get("heal_below", ""), row.get("lock", ""))


def index(rows: list[dict]) -> dict:
    out = defaultdict(dict)
    for row in rows:
        out[key_of(row)][(row["dex"], row["move"])] = row
    return out


def lifts(base: dict, treat: dict, field: str = "median_s") -> list[float]:
    vals = []
    for k, b in base.items():
        if k not in treat:
            continue
        b0 = fnum(b, field)
        if b0 <= 0:
            continue
        vals.append((fnum(treat[k], field) - b0) / b0)
    return vals


def show(label: str, vals: list[float]) -> None:
    if not vals:
        print(f"{label:28} (no rows)")
        return
    print(f"{label:28} n={len(vals):4}  med {100*median(vals):+6.1f}%  mean {100*mean(vals):+6.1f}%")


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "fixed_group"
    mech = json.loads(MECH.read_text())
    main_path = folder / "passives_g2p2.csv"
    if not main_path.exists():
        print("missing", main_path)
        return
    rows = load(main_path)
    by = index(rows)
    base_key = ("none", "", "", "", "")
    base = by[base_key]
    print(f"protocol rows {len(rows)} configs {len(by)} species {len(base)}")
    base_med = [fnum(r, "median_s") for r in base.values()]
    base_lvl = [fnum(r, "median_lvl") for r in base.values()]
    print(f"baseline median-of-medians {median(base_med):.1f}s  mean {mean(base_med):.1f}s  median level {median(base_lvl):.1f}")
    alive = {k: sum(int(r[k]) for r in base.values()) for k in ("alive180", "alive300", "alive600")}
    print(f"baseline runs reaching 3/5/10 min: {alive} of {len(base)*100}")

    print("\n== prefer / order / item (median survival) ==")
    for k in sorted(by, key=lambda t: (t[0], t[1], t[3], t[4])):
        if k == base_key:
            continue
        label = f"{k[0]} fill={k[1] or '-'} heal={k[3] or '-'} lock={k[4] or '-'}"
        show(label, lifts(base, by[k]))

    print("\n== p75 and p90 for single-stat prefers ==")
    for fill, name in NAMES.items():
        if not fill:
            continue
        k = ("none", fill, "", "", "")
        if k not in by:
            continue
        show(f"p75 {name}", lifts(base, by[k], "p75_s"))
        show(f"p90 {name}", lifts(base, by[k], "p90_s"))

    print("\n== by primary kind (protocol sample) ==")
    for kind in sorted({mech[mv]["kind"] for _, mv in base}):
        sub_b = {km: row for km, row in base.items() if mech[km[1]]["kind"] == kind}
        print(f"\n[{kind}] n={len(sub_b)}")
        for fill, name in [("2", "hp"), ("5", "rgn"), ("0", "atk"), ("4", "cd"), ("3", "def"), ("1", "spd"), ("7", "xp"), ("8", "heal")]:
            k = ("none", fill, "", "", "")
            if k not in by:
                continue
            sub_t = {km: row for km, row in by[k].items() if km in sub_b}
            show(f"  {name}", lifts(sub_b, sub_t))

    kinds_path = folder / "passives_kinds_g2p2.csv"
    if kinds_path.exists():
        print("\n== kind stratum (own baseline) ==")
        krows = load(kinds_path)
        kby = index(krows)
        kbase = kby[("none", "", "", "", "")]
        groups = defaultdict(dict)
        for (dex, move), row in kbase.items():
            groups[mech[move]["kind"]][(dex, move)] = row
        for kind, sub_b in sorted(groups.items()):
            print(f"\n[{kind}] n={len(sub_b)} base {median(fnum(r,'median_s') for r in sub_b.values()):.0f}s")
            for fill, name in [("2", "hp"), ("5", "rgn"), ("0", "atk"), ("4", "cd"), ("3", "def"), ("1", "spd")]:
                sub_t = {km: row for km, row in kby[("none", fill, "", "", "")].items() if km in sub_b}
                show(f"  {name}", lifts(sub_b, sub_t))

    first_path = folder / "passives_first_g2p2.csv"
    if first_path.exists():
        print("\n== first pick ==")
        wins = defaultdict(int)
        order = {"2": "hp", "5": "rgn", "1": "spd", "4": "cd", "3": "def", "": "atk"}
        grouped = defaultdict(dict)
        for row in load(first_path):
            grouped[row["dex"]][row["fill"]] = fnum(row, "median_s")
        for dex, opts in grouped.items():
            best = max(opts.items(), key=lambda kv: (kv[1], 0 if kv[0] == "" else -int(kv[0])))
            wins[order[best[0]]] += 1
        print(dict(wins), "total", sum(wins.values()))


if __name__ == "__main__":
    main()
