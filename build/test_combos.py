"""The bonded pair. Hex no longer leads just to pick up Lick; dash pairs stay.

    python3 -m unittest build/test_combos.py
"""
from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import combos  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _load():
    dex = {p["dex"]: p["types"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    with (DATA / "ranking_definitive.csv").open(encoding="utf8") as f:
        best = {int(r["dex"]): r["best_move"] for r in csv.DictReader(l for l in f if not l.startswith("#"))}
    return combos.compute_all(dex, best), best


class GroupSelector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups, cls.best = _load()
        cls.flags = combos._synergy_flags()

    def test_marshadow_bonds_shadow_ball_and_aura_sphere(self):
        self.assertEqual(
            self.groups[802]["moves"],
            ["shadow-ball", "aura-sphere", "swords-dance", "harden"],
        )

    def test_rotom_leads_thunder_shock_and_still_bonds_hex(self):
        # Thunder Shock does not burn, poison or slow, so Hex stays the coverage partner.
        self.assertEqual(self.groups[479]["moves"][:2], ["thunder-shock", "hex"])

    def test_scyther_keeps_the_dash_pair(self):
        self.assertEqual(self.groups[123]["moves"][:2], ["aerial-ace", "quick-attack"])

    def test_hex_does_not_drag_lick_into_the_bond(self):
        pairs = [g["moves"][:2] for g in self.groups.values()]
        self.assertNotIn(["hex", "lick"], pairs)
        dashes = [p for p in pairs if p == ["aerial-ace", "quick-attack"]]
        self.assertEqual(len(dashes), 10)

    def test_a_non_hex_best_move_still_leads(self):
        for dex, best in self.best.items():
            flag = self.flags.get(best)
            if flag and flag[0]:
                continue
            self.assertEqual(self.groups[dex]["moves"][0], best, dex)


if __name__ == "__main__":
    unittest.main()
