"""Card-priority runs for the pasivas page.

Protocol: the 150 species in results/fixed_group/items_g2p2.csv, fixed group 2+2,
100 seeds, --terrain --status --full-cards. Two scenarios: the repulse bot, and the
same bot ignoring half of each combat hit (--dodge 0.5).

Stat indices are data::STATS, then the cards --full-cards adds:
  0 atk, 1 spd, 2 hp, 3 def, 4 cd, 5 rgn, 6 mag, 7 xp, 8 heal.

A heal_below value with an empty fill is the Baya Zidra rule: take it, ahead of
stat cards, only while hp/maxHp is at or below that fraction (levelup.js:27).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "fixed_group"
ITEMS = OUT / "items_g2p2.csv"

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

# Thresholds Felipe asked for, plus always-take (1) as the comparison.
ZIDRA = ["0.30", "0.45", "0.55", "0.70", "1"]


def species(path: Path = ITEMS) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    got: set[str] = set()
    for row in csv.DictReader(path.open()):
        if row["dex"] in got or row["item"] != "none":
            continue
        got.add(row["dex"])
        seen.append((row["dex"], row["move"]))
    return seen


def line(dex: str, move: str, item: str = "none", fill: str = "", heal: str = "") -> str:
    return f"{dex},{move},{item},{fill},,,{heal}"


def zidra_tasks(path: Path) -> None:
    rows = [line(dex, move, heal=h) for dex, move in species() for h in ["", *ZIDRA]]
    path.write_text("\n".join(rows) + "\n", encoding="utf8")
    print(f"{path.name}: {len(rows)}")


def rank_tasks(path: Path, heal: str) -> None:
    """Prefer each stat, a few two-card orders, and the item pairs, with one Zidra rule."""
    fills = ["", "0", "1", "2", "3", "4", "5", "6", "7", "5;2", "2;5", "5;0", "2;0", "0;4", "4;0"]
    rows = [line(dex, move, fill=fill, heal=heal) for dex, move in species() for fill in fills]
    for dex, move in species():
        for item, fill in [
            ("assaultvest", ""),
            ("assaultvest", "3"),
            ("choiceband", ""),
            ("choiceband", "4"),
            ("choiceband", "0"),
            ("leftovers", ""),
            ("leftovers", "5"),
            ("leftovers", "2"),
            ("shellbell", ""),
            ("shellbell", "5"),
            ("quickclaw", ""),
            ("quickclaw", "4"),
        ]:
            rows.append(line(dex, move, item=item, fill=fill, heal=heal))
    path.write_text("\n".join(rows) + "\n", encoding="utf8")
    print(f"{path.name}: {len(rows)}")


def load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def index(rows: list[dict]) -> dict[tuple, dict]:
    out: dict[tuple, dict] = defaultdict(dict)
    for row in rows:
        key = (row["item"], row["fill"], row.get("heal_below", ""))
        out[key][(row["dex"], row["move"])] = row
    return out


def lifts(base: dict, treat: dict, field: str) -> list[float]:
    vals = []
    for k, b in base.items():
        if k not in treat:
            continue
        b0 = float(b[field])
        if b0 <= 0:
            continue
        vals.append((float(treat[k][field]) - b0) / b0)
    return vals


def med(rows: dict, field: str) -> float:
    return median(float(r[field]) for r in rows.values())


def show_block(by: dict, base_key: tuple) -> None:
    base = by[base_key]
    print(f"species {len(base)}")
    print(
        f"base  t={med(base,'median_s'):.1f}s  kills={med(base,'median_kills'):.1f}"
        f"  kpm={med(base,'median_kpm'):.2f}  bosses={med(base,'median_bosses'):.2f}"
        f"  lvl={med(base,'median_lvl'):.1f}  coins={med(base,'median_coins'):.1f}"
    )
    print(f"{'policy':28} {'t%':>7} {'coin%':>7} {'kpm%':>7} {'t':>7} {'kpm':>6} {'boss':>5} {'lvl':>5} {'coins':>7}")
    for key in sorted(by, key=lambda t: (t[0], t[1], t[2])):
        rows = by[key]
        label = f"{key[0]} fill={key[1] or '-'} heal={key[2] or '-'}"
        ts = lifts(base, rows, "median_s")
        cs = lifts(base, rows, "median_coins")
        ks = lifts(base, rows, "median_kpm")
        def pct(v: list[float]) -> str:
            return f"{100 * median(v):+6.1f}" if v else "   n/a"
        print(
            f"{label:28} {pct(ts):>7} {pct(cs):>7} {pct(ks):>7}"
            f" {med(rows,'median_s'):7.1f} {med(rows,'median_kpm'):6.2f}"
            f" {med(rows,'median_bosses'):5.2f} {med(rows,'median_lvl'):5.1f}"
            f" {med(rows,'median_coins'):7.1f}"
        )


def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print("usage: pasivas_rank.py zidra|rank <heal>|report <csv>...")
        return
    cmd = sys.argv[1]
    if cmd == "zidra":
        zidra_tasks(OUT / "pasivas_zidra_tasks.txt")
    elif cmd == "rank":
        rank_tasks(OUT / "pasivas_rank_tasks.txt", sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "report":
        for path in sys.argv[2:]:
            print(f"\n## {path}")
            rows = load(Path(path))
            by = index(rows)
            # baseline is the empty heal if present, else the first heal value
            heals = sorted({k[2] for k in by if k[0] == "none" and k[1] == ""})
            base_heal = "" if "" in heals else heals[0]
            show_block(by, ("none", "", base_heal))
    else:
        raise SystemExit(f"unknown {cmd}")


if __name__ == "__main__":
    main()
