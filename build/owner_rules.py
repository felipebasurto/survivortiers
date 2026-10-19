"""The owner's build rules, in one place.

`data/owner_rules.json` is the list. This module is what the publisher calls.
The sim reads the same ids (Danza Espada / Maquinación, Gengar) and the same
score idea: survival counts, damage and kills count, and a run that deals
nothing scores 0.

- Danza Espada for a physical lead, Maquinación for a special lead.
  A mixed group follows the lead attack's side.
- The fourth slot is Fortaleza or a third attack, whichever the sim scores higher.
- Gengar never keeps a melee move.
- Best move is an attacking move: it deals damage and it is not a buff.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "data" / "owner_rules.json").read_text(encoding="utf8"))

GENGAR_DEX = int(RULES["gengar_dex"])
PHYSICAL_BUFF = RULES["physical_buff"]
SPECIAL_BUFF = RULES["special_buff"]


def attack_buff(lead_cat: str, species_special: bool) -> str:
    """Buff id for a bonded group. `lead_cat` is physical, special, or empty."""
    if lead_cat == "special" or (not lead_cat and species_special):
        return SPECIAL_BUFF
    return PHYSICAL_BUFF


def allows_melee(dex: int) -> bool:
    return int(dex) != GENGAR_DEX


def is_attack(kind: str, dealt: float | None = None) -> bool:
    """True when a row can be the published best move.

    Buffs are not attacks. A row that dealt nothing is not either, whatever
    its kind: the run score of that fight is 0. Turret, orbit and melee are
    attacks when they deal damage.
    """
    if kind == "buff":
        return False
    if dealt is not None and dealt <= 0.0:
        return False
    return True
