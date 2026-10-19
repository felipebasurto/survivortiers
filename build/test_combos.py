"""The bonded attacks come from the fixed-group search, and the published buffs are the winner's.

    python3 build/test_combos.py

The tests check properties over all 966 groups, not a particular species' pick: the picks
move every time the sim is rerun.
"""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import combos
import picks

ROOT = Path(__file__).resolve().parent.parent


class Groups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dex = {p["dex"]: p["types"] for p in json.loads((ROOT / "data" / "pokedex_export.json").read_text())}
        with (ROOT / "data" / "ranking_definitive.csv").open(encoding="utf8") as f:
            best = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
        cls.groups = combos.compute_all(dex, best)
        cls.picked = combos._search_picks()

    def test_every_species_has_a_group(self):
        self.assertEqual(len(self.groups), 966)

    def test_searched_groups_fit_the_four_slots(self):
        self.assertGreater(len(self.picked), 900)
        for dex, (attacks, buffs) in self.picked.items():
            self.assertIn(len(attacks), (2, 3), (dex, attacks))
            self.assertLessEqual(len(attacks) + len(buffs), picks.BOND_SLOTS, (dex, attacks, buffs))

    def test_published_buffs_are_the_winning_groups(self):
        for dex, (attacks, buffs) in self.picked.items():
            group = self.groups[dex]
            if group["moves"][: len(group["moves"]) - group["nBoost"]] != attacks:
                continue
            self.assertEqual(group["moves"][len(group["moves"]) - group["nBoost"]:], buffs, dex)


class FallbackBuff(unittest.TestCase):
    cats = {"shadow-ball": "special", "lick": "physical", "tackle": "physical", "hex": "special"}
    available = ["dragon-dance", "nasty-plot", "swords-dance", "harden"]

    def test_buff_raises_the_first_attack(self):
        self.assertEqual(combos._attack_buff(["shadow-ball", "lick"], self.cats, False, self.available), "nasty-plot")
        self.assertEqual(combos._attack_buff(["tackle", "hex"], self.cats, True, self.available), "swords-dance")

    def test_uncategorised_group_falls_back_to_the_species_side(self):
        self.assertEqual(combos._attack_buff(["x", "y"], self.cats, True, self.available), "nasty-plot")
        self.assertEqual(combos._attack_buff(["x", "y"], self.cats, False, self.available), "swords-dance")


if __name__ == "__main__":
    unittest.main()
