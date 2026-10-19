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

    def test_marshadow_hex_with_lick(self):
        # After the physical/special split the search prefers Hex + Lick over Shadow Ball.
        self.assertEqual(self.attacks(802), ["hex", "lick"])

    def test_dash_pair_can_lead(self):
        self.assertEqual(self.attacks(123), ["aerial-ace", "body-slam"])
        self.assertEqual(self.attacks(189), ["aerial-ace", "quick-attack"])
        self.assertEqual(self.attacks(430), ["aerial-ace", "quick-attack"])

    def test_gengar_has_no_melee(self):
        attacks = self.attacks(94)
        self.assertNotIn("body-slam", attacks)
        self.assertTrue(all(move not in combos._MELEE for move in attacks))

    def test_species_outside_the_search_keeps_its_best_move(self):
        self.assertEqual(self.attacks(647)[0], "aura-sphere")


if __name__ == "__main__":
    unittest.main()
