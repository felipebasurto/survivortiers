"""The bonded attacks come from the fixed-group search, not from a tier-list rule.

    python3 build/test_combos.py
"""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import combos

ROOT = Path(__file__).resolve().parent.parent


class SearchPicks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dex = {p["dex"]: p["types"] for p in json.loads((ROOT / "data" / "pokedex_export.json").read_text())}
        with (ROOT / "data" / "ranking_definitive.csv").open(encoding="utf8") as f:
            best = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
        cls.groups = combos.compute_all(dex, best)

    def attacks(self, dex: int) -> list[str]:
        group = self.groups[dex]
        return group["moves"][: len(group["moves"]) - group["nBoost"]]

    def test_marshadow_shadow_ball_hex_and_aura_sphere(self):
        # Same median and mean as Shadow Ball + Hex + Swords Dance + Harden.
        # The group name breaks the tie, so the third attack takes the fourth slot.
        self.assertEqual(self.attacks(802), ["shadow-ball", "hex", "aura-sphere"])

    def test_dash_pair_can_lead(self):
        self.assertEqual(self.attacks(123), ["aerial-ace", "quick-attack"])
        self.assertEqual(self.attacks(189), ["aerial-ace", "quick-attack"])
        self.assertEqual(self.attacks(430), ["aerial-ace", "quick-attack"])

    def test_gengar_has_no_melee(self):
        attacks = self.attacks(94)
        self.assertNotIn("body-slam", attacks)
        self.assertTrue(all(move not in combos._MELEE for move in attacks))
        moves = self.groups[94]["moves"]
        self.assertIn("nasty-plot", moves)
        self.assertNotIn("swords-dance", moves)
        self.assertNotIn("dragon-dance", moves)

    def test_special_attack_groups_use_nasty_plot(self):
        for dex in (94, 647):
            moves = self.groups[dex]["moves"]
            self.assertIn("nasty-plot", moves)
            self.assertNotIn("swords-dance", moves)

    def test_physical_attack_group_keeps_swords_dance(self):
        # Onix's bonded attacks are physical, so Danza Espada still raises them.
        moves = self.groups[95]["moves"]
        self.assertIn("swords-dance", moves)
        self.assertNotIn("nasty-plot", moves)

    def test_marshadow_special_attacks_use_nasty_plot(self):
        moves = self.groups[802]["moves"]
        self.assertEqual(self.attacks(802), ["shadow-ball", "hex", "aura-sphere"])
        self.assertIn("nasty-plot", moves)
        self.assertNotIn("swords-dance", moves)

    def test_species_outside_the_search_keeps_its_best_move(self):
        self.assertEqual(self.attacks(647)[0], "aura-sphere")


if __name__ == "__main__":
    unittest.main()
