"""Which move and which group the sim picks for a species.

One function decides each, for the publisher (`make_definitive.py`, `combos.py`) and for
the staged search in `regen.py`. Both rank on the sim score (survival times damage and
kills, see `simulator/sim-rs/src/stats.rs`), adjusted for the owner's melee penalty.

A row is a candidate only when the owner's rules allow it (`owner_rules`):

- a move row is an attack that dealt damage; Sustituto never is, Gengar never gets melee;
- a group row holds two or three attacks of one category, the attack buff of that
  category (Danza Espada for physical, Maquinación for special) and, as the fourth slot,
  Fortaleza or a third attack. A group that mixes categories is never a candidate.

The pick is the highest adjusted median score. Ties break on the adjusted mean score,
kills and damage, and only then on fewer attacks and the id. There is no interval-overlap
tie rule: a 'cheaper group wins a tie' rule picked groups that scored lower.
"""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import owner_rules

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "simulator" / "v3" / "v3_data.json"

HARDEN_SLOTS = frozenset({"harden", "agility"})
BUFF_IDS = frozenset({"dragon-dance", "swords-dance", "harden", "agility", "nasty-plot"})


@lru_cache(maxsize=1)
def _v3_moves() -> dict:
    return json.loads(V3.read_text(encoding="utf8"))["moves"]


def kinds() -> dict[str, str]:
    return {mid: move["kind"] for mid, move in _v3_moves().items()}


def categories() -> dict[str, str]:
    """move id -> physical | special | '' (buffs). `moves.js` PHYSICAL set, through v3_data.json."""
    return {mid: (move["levels"][0].get("cat") or "") for mid, move in _v3_moves().items()}


def has_melee(attacks: Iterable[str]) -> bool:
    k = kinds()
    return any(k.get(a) == "melee" for a in attacks)


def load_rows(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _num(row: dict, key: str, fallback: str | None = None) -> float:
    raw = row.get(key)
    if raw in (None, "") and fallback:
        raw = row.get(fallback)
    return float(raw) if raw not in (None, "") else 0.0


def score(row: dict, melee: bool) -> float:
    return owner_rules.adjusted(_num(row, "median_score", "median_s"), melee)


def score_bounds(row: dict, melee: bool) -> tuple[float, float, float]:
    """Adjusted (median, low, high) of a row's score interval."""
    mid = _num(row, "median_score", "median_s")
    lo = _num(row, "score_lo", "boot_lo") if row.get("score_lo") not in (None, "") else mid
    hi = _num(row, "score_hi", "boot_hi") if row.get("score_hi") not in (None, "") else mid
    return tuple(owner_rules.adjusted(x, melee) for x in (mid, lo, hi))  # type: ignore[return-value]


def _order(row: dict, melee: bool, n_attacks: int, ident: str) -> tuple:
    return (
        -score(row, melee),
        -owner_rules.adjusted(_num(row, "mean_score", "mean_s"), melee),
        -_num(row, "median_kills"),
        -_num(row, "median_dealt"),
        -_num(row, "median_s"),
        n_attacks,
        ident,
    )


# ---------------------------------------------------------------------------- one move

def move_ok(dex: int, row: dict) -> bool:
    move = row["start"]
    if not owner_rules.is_attack(move, row.get("kind") or "", _num(row, "median_dealt") if row.get("median_dealt") not in (None, "") else None):
        return False
    return owner_rules.allows_melee(dex) or row.get("kind") != "melee"


def move_order(row: dict) -> tuple:
    return _order(row, row.get("kind") == "melee", 1, row["start"])


def best_moves(rows: list[dict]) -> dict[int, dict]:
    """dex -> the best attacking move row."""
    pools: dict[int, list[dict]] = {}
    for row in rows:
        dex = int(row["dex"])
        if move_ok(dex, row):
            pools.setdefault(dex, []).append(row)
    return {dex: min(pool, key=move_order) for dex, pool in pools.items()}


def shortlist_moves(rows: list[dict], k: int) -> dict[int, list[dict]]:
    pools: dict[int, list[dict]] = {}
    for row in rows:
        dex = int(row["dex"])
        if move_ok(dex, row):
            pools.setdefault(dex, []).append(row)
    return {dex: sorted(pool, key=move_order)[:k] for dex, pool in pools.items()}


# --------------------------------------------------------------------------- one group

def split_group(group: str) -> tuple[list[str], str | None, str | None]:
    """(attacks, attack buff id, fourth-slot buff id) of a searched group name."""
    attacks, attack_buff, fourth = [], None, None
    for part in group.split("+"):
        if part in owner_rules.ATTACK_BUFFS or part == "dragon-dance":
            attack_buff = part
        elif part in HARDEN_SLOTS:
            fourth = part
        else:
            attacks.append(part)
    return attacks, attack_buff, fourth


def group_ok(dex: int, group: str) -> bool:
    attacks, buff, _ = split_group(group)
    if buff is None or len(attacks) < 2:
        return False
    if any(a in owner_rules.NEVER_ATTACK for a in attacks):
        return False
    if not owner_rules.allows_melee(dex) and has_melee(attacks):
        return False
    cat = owner_rules.group_category(attacks, categories())
    return cat is not None and owner_rules.attack_buff(cat) == buff


def group_order(row: dict) -> tuple:
    attacks, _, _ = split_group(row["group"])
    return _order(row, has_melee(attacks), len(attacks), row["group"])


def best_groups(rows: list[dict]) -> dict[int, dict]:
    """dex -> the best valid group row."""
    pools: dict[int, list[dict]] = {}
    for row in rows:
        dex = int(row["dex"])
        if group_ok(dex, row["group"]):
            pools.setdefault(dex, []).append(row)
    return {dex: min(pool, key=group_order) for dex, pool in pools.items()}


def shortlist_groups(rows: list[dict], per_shape: int) -> dict[int, list[dict]]:
    """The best `per_shape` groups with Fortaleza as the fourth slot and the best
    `per_shape` with a third attack, so the last stage settles the two shapes head to head."""
    pools: dict[int, dict[str, list[dict]]] = {}
    for row in rows:
        dex = int(row["dex"])
        if not group_ok(dex, row["group"]):
            continue
        _, _, fourth = split_group(row["group"])
        shape = "harden" if fourth else "third"
        pools.setdefault(dex, {}).setdefault(shape, []).append(row)
    out: dict[int, list[dict]] = {}
    for dex, shapes in pools.items():
        picked: list[dict] = []
        for shape in ("harden", "third"):
            picked.extend(sorted(shapes.get(shape, []), key=group_order)[:per_shape])
        out[dex] = picked
    return out
