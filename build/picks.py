"""Which move and which group the sim picks for a species.

One function decides each, for the publisher (`make_definitive.py`, `combos.py`) and for
the staged search in `regen.py`. Both rank on the sim score (survival times damage and
kills, see `simulator/sim-rs/src/stats.rs`) as measured.

- A move row is a candidate when it is an attack (not a buff) that dealt damage.
- A group row is a candidate when it bonds two or three attacks inside the four slots.
  Its buffs, categories and shape are whatever the search tried; the score picks.

The pick is the highest median score. Ties break on the mean score, kills and damage, and
only then on fewer attacks and the id. There is no interval-overlap tie rule: a 'cheaper
group wins a tie' rule picked groups that scored lower.
"""
from __future__ import annotations

import csv
import math
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "simulator" / "v3" / "v3_data.json"
BOND_SLOTS = 4
# Grupos por (especie, forma) que pasan de la criba de 16 semillas al afinado de 96. Lo usan regen.py y builds.py.
REFINE_PER_SHAPE = 2


@lru_cache(maxsize=1)
def _v3_moves() -> dict:
    return json.loads(V3.read_text(encoding="utf8"))["moves"]


@lru_cache(maxsize=1)
def attack_buff_side() -> dict[str, str]:
    """attack buff id -> the category it raises (moves.js stat patk / satk)."""
    side = {"patk": "physical", "satk": "special"}
    return {
        mid: side[move["levels"][0]["stat"]]
        for mid, move in _v3_moves().items()
        if move["kind"] == "buff" and move["levels"][0].get("stat") in side
    }


def kinds() -> dict[str, str]:
    return {mid: move["kind"] for mid, move in _v3_moves().items()}


def categories() -> dict[str, str]:
    """move id -> physical | special | '' (buffs). `moves.js` PHYSICAL set, through v3_data.json."""
    return {mid: (move["levels"][0].get("cat") or "") for mid, move in _v3_moves().items()}


def load_rows(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _num(row: dict, key: str, fallback: str | None = None) -> float:
    raw = row.get(key)
    if raw in (None, "") and fallback:
        raw = row.get(fallback)
    return float(raw) if raw not in (None, "") else 0.0


def score(row: dict) -> float:
    return _num(row, "median_score", "median_s")


def score_bounds(row: dict) -> tuple[float, float, float]:
    """(median, low, high) of a row's score interval."""
    mid = score(row)
    lo = _num(row, "score_lo", "boot_lo") if row.get("score_lo") not in (None, "") else mid
    hi = _num(row, "score_hi", "boot_hi") if row.get("score_hi") not in (None, "") else mid
    return mid, lo, hi


def _order(row: dict, n_attacks: int, ident: str) -> tuple:
    return (
        -score(row),
        -_num(row, "mean_score", "mean_s"),
        -_num(row, "median_kills"),
        -_num(row, "median_dealt"),
        -_num(row, "median_s"),
        n_attacks,
        ident,
    )


# ---------------------------------------------------------------------------- one move

def is_attack(kind: str, dealt: float | None = None) -> bool:
    """Not a buff, and it dealt damage when the row says how much (a run that deals nothing scores 0)."""
    return kind != "buff" and (dealt is None or dealt > 0.0)


def move_ok(row: dict) -> bool:
    dealt = _num(row, "median_dealt") if row.get("median_dealt") not in (None, "") else None
    return is_attack(row.get("kind") or "", dealt)


def move_order(row: dict) -> tuple:
    return _order(row, 1, row["start"])


def best_moves(rows: list[dict]) -> dict[int, dict]:
    """dex -> the best attacking move row."""
    pools: dict[int, list[dict]] = {}
    for row in rows:
        if move_ok(row):
            pools.setdefault(int(row["dex"]), []).append(row)
    return {dex: min(pool, key=move_order) for dex, pool in pools.items()}


def shortlist_moves(rows: list[dict], k: int) -> dict[int, list[dict]]:
    pools: dict[int, list[dict]] = {}
    for row in rows:
        if move_ok(row):
            pools.setdefault(int(row["dex"]), []).append(row)
    return {dex: sorted(pool, key=move_order)[:k] for dex, pool in pools.items()}


# --------------------------------------------------------------------------- one group

def split_group(group: str) -> tuple[list[str], list[str]]:
    """(attacks, buffs) of a searched group name, in the order the name gives them. A buff is any move of
    kind buff; which stat it raises is the game's business (attack_buff_side only classifies it)."""
    k = kinds()
    attacks, buffs = [], []
    for part in group.split("+"):
        (buffs if k.get(part) == "buff" else attacks).append(part)
    return attacks, buffs


def group_ok(group: str) -> bool:
    """Two or three attacks, at most two buffs (levelup.js:47-49), and the four bond slots of the simulator."""
    attacks, buffs = split_group(group)
    return len(attacks) >= 2 and len(buffs) <= 2 and len(attacks) + len(buffs) <= BOND_SLOTS


def shape_of(group: str) -> str:
    """'<attacks>+<buffs>', for example '2+2' or '3+1'."""
    attacks, buffs = split_group(group)
    return f"{len(attacks)}+{len(buffs)}"


def group_order(row: dict) -> tuple:
    attacks, _ = split_group(row["group"])
    return _order(row, len(attacks), row["group"])


def best_groups(rows: list[dict]) -> dict[int, dict]:
    """dex -> the best valid group row."""
    pools: dict[int, list[dict]] = {}
    for row in rows:
        if group_ok(row["group"]):
            pools.setdefault(int(row["dex"]), []).append(row)
    return {dex: min(pool, key=group_order) for dex, pool in pools.items()}


def halving_keep(rows: list[dict], keep_frac: float, min_keep: int) -> list[tuple[str, str]]:
    """The (dex, group) pairs that move from the short screen to the full one. Per species and
    shape, keep the best max(min_keep, ceil(keep_frac * n)) groups in shortlist order."""
    pools: dict[tuple[int, str], list[dict]] = {}
    for row in rows:
        if not group_ok(row["group"]):
            continue
        pools.setdefault((int(row["dex"]), shape_of(row["group"])), []).append(row)
    keep: list[tuple[str, str]] = []
    for pool in pools.values():
        n = max(min_keep, math.ceil(keep_frac * len(pool)))
        keep.extend((row["dex"], row["group"]) for row in sorted(pool, key=group_order)[:n])
    return sorted(keep, key=lambda k: (int(k[0]), k[1]))


def shortlist_groups(rows: list[dict], per_shape: int) -> dict[int, list[dict]]:
    """The best `per_shape` groups of each shape (`shape_of`), so the last stage settles the
    shapes head to head."""
    pools: dict[int, dict[str, list[dict]]] = {}
    for row in rows:
        if not group_ok(row["group"]):
            continue
        pools.setdefault(int(row["dex"]), {}).setdefault(shape_of(row["group"]), []).append(row)
    out: dict[int, list[dict]] = {}
    for dex, shapes in pools.items():
        picked: list[dict] = []
        for shape in sorted(shapes):
            picked.extend(sorted(shapes[shape], key=group_order)[:per_shape])
        out[dex] = picked
    return out
