"""The published best move is an attack that dealt damage, picked on the sim score alone.

    python3 build/test_best_move.py
"""
from __future__ import annotations

import unittest
from pathlib import Path

import make_definitive as md

ROOT = Path(__file__).resolve().parent.parent
SOLO = ROOT / "simulator" / "results" / "fixed_group" / "solo_sweep.csv"
SCREEN = ROOT / "simulator" / "results" / "fixed_group" / "solo_screen.csv"


class BestMove(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = md.load_csv(SOLO)
        cls.winners = md.winner_by_dex(cls.rows)

    def test_every_species_has_a_best_move(self):
        self.assertEqual(len(self.winners), 966)

    def test_substitute_rows_deal_damage(self):
        subs = [row for row in md.load_csv(SCREEN) if row["start"] == "substitute"]
        self.assertGreater(len(subs), 200)
        self.assertTrue(all(float(row["median_dealt"]) > 0 for row in subs))
        self.assertTrue(all(row["kind"] == "turret" for row in subs))

    def test_a_buff_cannot_win_and_a_turret_competes_on_its_score(self):
        buff = {
            "dex": "2",
            "start": "swords-dance",
            "kind": "buff",
            "median_s": "200",
            "mean_s": "200",
            "median_score": "999",
            "mean_score": "999",
            "median_dealt": "0",
        }
        turret = {
            "dex": "2",
            "start": "substitute",
            "kind": "turret",
            "median_s": "50",
            "mean_s": "50",
            "median_score": "10",
            "mean_score": "10",
            "median_dealt": "40",
        }
        real = dict(turret, start="water-gun", kind="projectile", median_score="1", mean_score="1")
        self.assertEqual(md.winner_by_dex([buff, turret, real])[2]["start"], "substitute")
        self.assertEqual(md.winner_by_dex([buff, real])[2]["start"], "water-gun")
        self.assertNotIn(2, md.winner_by_dex([buff]))

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
