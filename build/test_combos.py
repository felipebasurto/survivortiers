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

    def test_marshadow_shadow_ball_aura_sphere_and_hex(self):
        # Maquinación rescore: Shadow Ball + Aura Sphere + Hex beats the Hex-led tie.
        # Lick is melee, so the melee-risk rule does not publish it.
        self.assertEqual(self.attacks(802), ["shadow-ball", "aura-sphere", "hex"])

    def test_dash_pair_can_lead(self):
        self.assertEqual(self.attacks(123), ["aerial-ace", "quick-attack"])
        # Jumpluff's vine whip cleared the melee floor: its bootstrap floor beats the best
        # ranged median and the mean is not worse. Hyper Voice is the ranged runner-up.
        self.assertEqual(self.attacks(189), ["aerial-ace", "vine-whip"])
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
        self.assertEqual(self.attacks(802), ["shadow-ball", "aura-sphere", "hex"])
        self.assertIn("nasty-plot", moves)
        self.assertNotIn("swords-dance", moves)

    def test_species_outside_the_search_keeps_its_best_move(self):
        self.assertEqual(self.attacks(647)[0], "aura-sphere")

    def test_buff_follows_the_lead_attack(self):
        cats = {"shadow-ball": "special", "lick": "physical", "tackle": "physical", "hex": "special"}
        available = ["nasty-plot", "swords-dance", "harden"]
        self.assertEqual(
            combos._attack_buff(["shadow-ball", "hex"], "swords-dance", cats, False, available),
            "nasty-plot",
        )
        self.assertEqual(
            combos._attack_buff(["tackle", "lick"], "nasty-plot", cats, True, available),
            "swords-dance",
        )
        # Mixed pair: the lead decides, even when the searched buff and the species side disagree.
        self.assertEqual(
            combos._attack_buff(["shadow-ball", "lick"], "swords-dance", cats, False, available),
            "nasty-plot",
        )
        self.assertEqual(
            combos._attack_buff(["lick", "shadow-ball"], "nasty-plot", cats, True, available),
            "swords-dance",
        )


if __name__ == "__main__":
    unittest.main()
