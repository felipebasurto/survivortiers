"""The published best move is an attack. Sustituto stays in the sweep and loses the pick.

    python3 build/test_best_move.py
"""
from __future__ import annotations

import unittest
from pathlib import Path

import make_definitive as md

ROOT = Path(__file__).resolve().parent.parent
SOLO = ROOT / "simulator" / "results" / "fixed_group" / "solo_sweep.csv"


class BestMove(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = md.load_csv(SOLO)
        cls.winners = md.winner_by_dex(cls.rows)

    def test_substitute_rows_deal_damage(self):
        subs = [row for row in self.rows if row["start"] == "substitute"]
        self.assertGreater(len(subs), 200)
        self.assertTrue(all(float(row["median_dealt"]) > 0 for row in subs))
        self.assertTrue(all(row["kind"] == "turret" for row in subs))

    def test_no_species_publishes_substitute(self):
        dexes = {int(row["dex"]) for row in self.rows}
        self.assertEqual(set(self.winners), dexes)
        bad = [
            dex
            for dex, row in self.winners.items()
            if row["start"] == "substitute" or row["kind"] in ("turret", "buff", "orbit")
        ]
        self.assertEqual(bad, [])

    def test_gengar_best_move_is_not_melee(self):
        row = self.winners[94]
        self.assertNotEqual(row["kind"], "melee")
        self.assertNotEqual(row["start"], "substitute")

    def test_a_zero_damage_row_cannot_win(self):
        ghost = {
            "dex": "1",
            "start": "tackle",
            "kind": "melee",
            "median_s": "100",
            "mean_s": "100",
            "median_score": "999",
            "mean_score": "999",
            "median_dealt": "0",
        }
        real = {
            "dex": "1",
            "start": "vine-whip",
            "kind": "melee",
            "median_s": "10",
            "mean_s": "10",
            "median_score": "1",
            "mean_score": "1",
            "median_dealt": "5",
        }
        self.assertEqual(md.winner_by_dex([ghost, real])[1]["start"], "vine-whip")


if __name__ == "__main__":
    unittest.main()
