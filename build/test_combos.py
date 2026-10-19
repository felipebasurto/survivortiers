"""The bonded attacks come from the fixed-group search and obey the owner's rules.

    python3 build/test_combos.py

The tests check rules over all 966 groups, not a particular species' pick: the picks move
every time the sim is rerun, the rules do not.
"""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import combos
import owner_rules
import picks

ROOT = Path(__file__).resolve().parent.parent
GENGAR = owner_rules.GENGAR_DEX


class GroupRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dex = {p["dex"]: p["types"] for p in json.loads((ROOT / "data" / "pokedex_export.json").read_text())}
        with (ROOT / "data" / "ranking_definitive.csv").open(encoding="utf8") as f:
            best = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
        cls.groups = combos.compute_all(dex, best)
        cls.cats = picks.categories()
        cls.kinds = picks.kinds()

    def attacks(self, dex: int) -> list[str]:
        group = self.groups[dex]
        return group["moves"][: len(group["moves"]) - group["nBoost"]]

    def boosts(self, dex: int) -> list[str]:
        group = self.groups[dex]
        return group["moves"][len(group["moves"]) - group["nBoost"]:]

    def test_every_species_has_a_group(self):
        self.assertEqual(len(self.groups), 966)

    def test_sustituto_is_never_in_a_group(self):
        for dex in self.groups:
            self.assertFalse(set(self.groups[dex]["moves"]) & owner_rules.NEVER_ATTACK, dex)
            self.assertFalse(set(self.groups[dex]["alts"]) & owner_rules.NEVER_ATTACK, dex)

    def test_attack_buff_matches_the_attacks(self):
        for dex in self.groups:
            cat = owner_rules.group_category(self.attacks(dex), self.cats)
            if cat is None:
                continue
            self.assertIn(owner_rules.attack_buff(cat), self.boosts(dex), (dex, self.attacks(dex)))
            other = owner_rules.PHYSICAL_BUFF if cat == "special" else owner_rules.SPECIAL_BUFF
            self.assertNotIn(other, self.boosts(dex), dex)

    def test_searched_groups_do_not_mix_categories(self):
        picked = combos._search_picks()
        self.assertGreater(len(picked), 900)
        for dex, (attacks, _, _) in picked.items():
            self.assertIsNotNone(owner_rules.group_category(attacks, self.cats), (dex, attacks))

    def test_gengar_has_no_melee(self):
        self.assertFalse(any(self.kinds.get(a) == "melee" for a in self.attacks(GENGAR)))
        self.assertFalse(any(self.kinds.get(a) == "melee" for a in self.groups[GENGAR]["alts"]))

    def test_searched_group_has_two_or_three_attacks(self):
        for dex, (attacks, with_harden, buff) in combos._search_picks().items():
            self.assertEqual(len(attacks), 2 if with_harden else 3, (dex, attacks, with_harden))
            self.assertIn(buff, owner_rules.ATTACK_BUFFS)

    def test_third_attack_is_chosen_for_some_species(self):
        picked = combos._search_picks()
        self.assertGreater(sum(1 for _, h, _ in picked.values() if not h), 0)
        self.assertGreater(sum(1 for _, h, _ in picked.values() if h), 0)


class BuffChoice(unittest.TestCase):
    cats = {"shadow-ball": "special", "lick": "physical", "tackle": "physical", "hex": "special"}
    available = ["nasty-plot", "swords-dance", "harden"]

    def test_buff_follows_the_category(self):
        self.assertEqual(combos._attack_buff(["shadow-ball", "hex"], self.cats, False, self.available), "nasty-plot")
        self.assertEqual(combos._attack_buff(["tackle", "lick"], self.cats, True, self.available), "swords-dance")

    def test_uncategorised_group_falls_back_to_the_species_side(self):
        self.assertEqual(combos._attack_buff(["x", "y"], self.cats, True, self.available), "nasty-plot")
        self.assertEqual(combos._attack_buff(["x", "y"], self.cats, False, self.available), "swords-dance")


if __name__ == "__main__":
    unittest.main()
