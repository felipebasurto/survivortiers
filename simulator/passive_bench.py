"""Build the passive-card task lists for the fixed 2+2 benchmark.

Protocol matches the item benchmark: the 150 species in results/fixed_group/items_g2p2.csv,
100 seeds, --group 2+2 --terrain --status --full-cards, partners from solo_sweep.csv.
A second list covers every species at 40 seeds, one row per first-stat priority, to re-check
the old first-pick counts.

Stat indices follow data::STATS, then the two cards --full-cards adds:
  0 atk, 1 spd, 2 hp, 3 def, 4 cd, 5 rgn, 6 mag, 7 xp, 8 heal.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ITEMS = ROOT / "results" / "fixed_group" / "items_g2p2.csv"
FILL = ROOT / "results" / "fixed_group" / "fill_g2p2.csv"
OUT = ROOT / "results" / "fixed_group"


def species(path: Path) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    got = set()
    for row in csv.DictReader(path.open()):
        if row["dex"] in got:
            continue
        if path == ITEMS and row["item"] != "none":
            continue
        got.add(row["dex"])
        seen.append((row["dex"], row["move"]))
    return seen


def line(dex: str, move: str, item: str = "none", fill: str = "", stop: str = "", heal: str = "", lock: str = "") -> str:
    return f"{dex},{move},{item},{fill},,{stop},{heal},{lock}"


def configs() -> list[tuple[str, dict]]:
    """(tag, columns). tag is not written; the columns identify the row."""
    out: list[tuple[str, dict]] = [("base", {})]
    for idx, name in enumerate(["atk", "spd", "hp", "def", "cd", "rgn", "mag", "xp"]):
        out.append((f"prefer-{name}", {"fill": str(idx)}))
    out.append(("prefer-heal", {"fill": "8"}))
    out.append(("prefer-heal-hurt", {"fill": "8", "heal": "0.55"}))
    for tag, fill in [
        ("order-hp-atk", "2;0"),
        ("order-atk-hp", "0;2"),
        ("order-rgn-hp", "5;2"),
        ("order-hp-rgn", "2;5"),
        ("order-cd-atk", "4;0"),
        ("order-atk-cd", "0;4"),
        ("order-def-hp", "3;2"),
        ("order-rgn-atk", "5;0"),
    ]:
        out.append((tag, {"fill": fill}))
    for idx, name in [(0, "atk"), (2, "hp"), (3, "def"), (4, "cd"), (5, "rgn")]:
        for n in (0, 1, 2, 4):
            out.append((f"lock-{name}-{n}", {"lock": f"{idx}:{n}"}))
    for item, fill, tag in [
        ("assaultvest", "", "item-vest"),
        ("assaultvest", "3", "item-vest-def"),
        ("choiceband", "", "item-band"),
        ("choiceband", "4", "item-band-cd"),
        ("choiceband", "0", "item-band-atk"),
        ("leftovers", "", "item-left"),
        ("leftovers", "5", "item-left-rgn"),
        ("leftovers", "2", "item-left-hp"),
        ("shellbell", "", "item-bell"),
        ("shellbell", "5", "item-bell-rgn"),
        ("shellbell", "0", "item-bell-atk"),
        ("quickclaw", "", "item-claw"),
        ("quickclaw", "4", "item-claw-cd"),
    ]:
        out.append((tag, {"item": item, "fill": fill}))
    return out


def write_protocol(path: Path) -> None:
    mons = species(ITEMS)
    rows = []
    for dex, move in mons:
        for _tag, cols in configs():
            rows.append(line(dex, move, cols.get("item", "none"), cols.get("fill", ""), cols.get("stop", ""), cols.get("heal", ""), cols.get("lock", "")))
    path.write_text("\n".join(rows) + "\n", encoding="utf8")
    print(f"{path.name}: {len(mons)} species x {len(configs())} configs = {len(rows)}")


def write_first(path: Path) -> None:
    """One row per species for the default order and for each combat stat taken first."""
    mons = species(FILL)
    fills = ["", "1", "2", "3", "4", "5"]
    rows = [line(dex, move, fill=fill) for dex, move in mons for fill in fills]
    path.write_text("\n".join(rows) + "\n", encoding="utf8")
    print(f"{path.name}: {len(mons)} species x {len(fills)} = {len(rows)}")


if __name__ == "__main__":
    import sys
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    dest.mkdir(parents=True, exist_ok=True)
    write_protocol(dest / "passives_tasks.txt")
    write_first(dest / "passives_first_tasks.txt")
