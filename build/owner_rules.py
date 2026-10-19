"""The owner's build rules, in one place.

`data/owner_rules.json` is the list. This module is what the publisher calls; the
engine reads the same file (`simulator/sim-rs/src/rules.rs`). The sim and the publisher
share the ids, the melee factor and the score idea: survival counts, damage and kills
count, and a run that deals nothing scores 0. None of these constants is a game number.

- A bonded group holds the attack buff that matches its attacks: Danza Espada for
  physical, Maquinación for special. A group never mixes the two categories.
- The fourth slot is Fortaleza or a third attack, whichever the sim scores higher.
- Gengar never keeps a melee move.
- Sustituto is never an attack: not a best move, not a group member.
- Best move is an attacking move: it deals damage and it is not a buff.
- The sim overrates melee, so a score that bonds a melee attack is multiplied by
  `melee_score_factor` before anything is compared.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "data" / "owner_rules.json").read_text(encoding="utf8"))

GENGAR_DEX = int(RULES["gengar_dex"])
PHYSICAL_BUFF = RULES["physical_buff"]
SPECIAL_BUFF = RULES["special_buff"]
NEVER_ATTACK = frozenset(RULES["never_attack"])
MELEE_SCORE_FACTOR = float(RULES["melee_score_factor"])
ATTACK_BUFFS = (SPECIAL_BUFF, PHYSICAL_BUFF)
BUFF_FOR_CATEGORY = {"physical": PHYSICAL_BUFF, "special": SPECIAL_BUFF}


def attack_buff(category: str) -> str:
    """Buff id for a bonded group whose attacks are all of `category`."""
    return BUFF_FOR_CATEGORY[category]


def group_category(attacks: Iterable[str], cats: Mapping[str, str]) -> str | None:
    """`physical` or `special` when every attack shares that category, else None (mixed)."""
    found = {cats.get(a) or "" for a in attacks}
    if len(found) == 1:
        (only,) = found
        if only in BUFF_FOR_CATEGORY:
            return only
    return None


def allows_melee(dex: int) -> bool:
    return int(dex) != GENGAR_DEX


def is_attack(move_id: str, kind: str, dealt: float | None = None) -> bool:
    """True when a row can be the published best move.

    Buffs are not attacks. Sustituto is not one either, even though its turret deals
    damage. A row that dealt nothing is not an attack: the run score of that fight is 0.
    Turret, orbit and melee are attacks when they deal damage.
    """
    if kind == "buff" or move_id in NEVER_ATTACK:
        return False
    if dealt is not None and dealt <= 0.0:
        return False
    return True


def adjusted(score: float, has_melee: bool) -> float:
    """The score as it is ranked. A melee attack in the run takes the owner's penalty."""
    return score * MELEE_SCORE_FACTOR if has_melee else score
