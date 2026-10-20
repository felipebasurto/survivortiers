"""Per-species card order for the Pokémon pages.

Same protocol as the pasivas ranking: each species' starting move, fixed group 2+2,
--terrain --status --full-cards, Baya Zidra at <=70% HP on every row
(--heal-below 0.70), partners from results/fixed_group/solo_sweep.csv, 100 seeds.
One row per stat card (fill 0 atk … 7 xp).

Order is median coins, then median survival, then mean survival, then the fill index.
Coins are the sim's combined score (round(floor(time/5)+floor(kills*0.25)+bosses*80+picked)).

    python3 card_priority.py tasks [out.txt]
    python3 card_priority.py order <cards.csv> [passive_sim.json]
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RANKING = ROOT / "data" / "ranking_definitive.csv"
PASSIVE = ROOT / "data" / "passive_sim.json"
# Evolution card of each move: Moves.EVO in the vendored game
# (simulator/vendor/pokesurvivor-5a23d49/js/data/moves.js, commit 5a23d49),
# extracted into v3/v3_data.json by simulator/v3/extract_v3.js.
GAME = ROOT / "simulator" / "v3" / "v3_data.json"
STATS = ["atk", "spd", "hp", "def", "cd", "rgn", "mag", "xp"]


def starting_moves() -> list[tuple[str, str]]:
    rows = []
    seen: set[str] = set()
    with RANKING.open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(line for line in f if not line.startswith("#")):
            dex, move = row["dex"], row["start_move"]
            if dex in seen:
                continue
            seen.add(dex)
            rows.append((dex, move))
    rows.sort(key=lambda t: int(t[0]))
    return rows


def task_lines() -> list[str]:
    """dex,move,item,fill,buffs,stop,heal_below,lock — heal 0.70 on every card."""
    return [f"{dex},{move},none,{fill},,,0.70," for dex, move in starting_moves() for fill in range(len(STATS))]


def order_key(row: dict) -> tuple:
    """Coins first. A tie breaks on survival, then kills per minute, then the fill index."""
    kpm = row.get("median_kpm")
    kpm_v = float(kpm) if kpm not in (None, "") else float(row.get("median_kills") or 0)
    return (
        -float(row["median_coins"]),
        -float(row["median_s"]),
        -float(row.get("mean_s") or 0),
        -kpm_v,
        int(row["fill"]),
    )


def order_of(rows: list[dict]) -> list[str]:
    return [STATS[int(r["fill"])] for r in sorted(rows, key=order_key)]


def orders_from(path: Path) -> dict[str, list[str]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            if row["item"] != "none" or row.get("heal_below", "") != "0.70":
                continue
            if row["fill"] not in {str(i) for i in range(len(STATS))}:
                continue
            grouped[row["dex"]].append(row)
    out = {}
    for dex, rows in grouped.items():
        fills = {r["fill"] for r in rows}
        if fills != {str(i) for i in range(len(STATS))}:
            raise SystemExit(f"{dex}: fills {sorted(fills)}, expected 0..7")
        out[dex] = order_of(rows)
    return out


def evolution_needs() -> dict[str, str]:
    """Move id -> stat card that evolves it. Source: Moves.EVO in the vendored game at 5a23d49,
    via the extract in v3/v3_data.json (simulator/v3/extract_v3.js reads js/data/moves.js)."""
    raw = json.loads(GAME.read_text(encoding="utf8"))
    needs = {}
    for mid, move in raw["moves"].items():
        card = move.get("needs")
        if not card:
            continue
        if card not in STATS:
            raise SystemExit(f"{mid}: evolution card {card!r} is not a stat card")
        needs[mid] = card
    if len(needs) != 97:
        raise SystemExit(f"v3_data.json has {len(needs)} evolving moves, expected the 97 attacks")
    return dict(sorted(needs.items()))


def write_order(csv_path: Path, json_path: Path) -> dict[str, int]:
    fresh = orders_from(csv_path)
    if len(fresh) != 966:
        raise SystemExit(f"{csv_path} has {len(fresh)} species, expected 966")
    needs = evolution_needs()
    counts: dict[str, int] = defaultdict(int)
    for order in fresh.values():
        counts[order[0]] += 1
    picks = ", ".join(f"{name} {counts[name]}" for name in STATS if counts[name])
    note = (
        "fixed-group sim (--group 2+2 --terrain --status --full-cards --bot repulse --heal-below 0.70; "
        "100 seeds; partners solo_sweep.csv): card ids by median coins when that stat is taken first, "
        "then median survival, then mean. Coins = round(floor(time/5)+floor(kills*0.25)+bosses*80+picked). "
        "Zidra is taken at <=70% HP in every run. "
        f"First picks: {picks}. needs: evolution card per move, from Moves.EVO in "
        "js/data/moves.js at 5a23d49 (vendored; extracted in simulator/v3/v3_data.json). "
        "The page lists all eight in this order and marks the card the lead attack needs to evolve "
        "(build/passives.py priority). Estimates."
    )
    doc = {"note": note, "needs": needs, "order": {d: fresh[d] for d in sorted(fresh, key=int)}}
    json_path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8")
    return counts


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: card_priority.py tasks [out] | order <csv> [json]")
    cmd = sys.argv[1]
    if cmd == "tasks":
        lines = task_lines()
        dest = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        text = "\n".join(lines) + "\n"
        if dest:
            dest.write_text(text, encoding="utf8")
        else:
            sys.stdout.write(text)
        print(f"{len(lines)} tasks", file=sys.stderr)
    elif cmd == "order":
        csv_path = Path(sys.argv[2])
        json_path = Path(sys.argv[3]) if len(sys.argv) > 3 else PASSIVE
        counts = write_order(csv_path, json_path)
        print(f"wrote {json_path}")
        print("first", dict(counts))
    else:
        raise SystemExit(f"unknown {cmd}")


if __name__ == "__main__":
    main()
