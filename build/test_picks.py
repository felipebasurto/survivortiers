"""The pick functions, on small synthetic tables.

    python3 build/test_picks.py
"""
from __future__ import annotations

import unittest

import picks


def move_row(dex, start, kind, score, dealt=100.0, kills=10.0):
    return {"dex": str(dex), "start": start, "kind": kind, "median_score": str(score), "median_s": "600",
            "mean_score": str(score), "median_dealt": str(dealt), "median_kills": str(kills)}


def group_row(dex, group, score, kills=10.0):
    return {"dex": str(dex), "group": group, "median_score": str(score), "median_s": "600",
            "mean_score": str(score), "median_dealt": "100", "median_kills": str(kills)}


class Attacks(unittest.TestCase):
    def test_buffs_and_zero_damage_are_not_attacks(self):
        self.assertFalse(picks.is_attack("buff"))
        self.assertFalse(picks.is_attack("projectile", 0.0))
        self.assertTrue(picks.is_attack("turret", 500.0))
        self.assertTrue(picks.is_attack("melee", 500.0))

    def test_buff_sides_come_from_the_game(self):
        side = picks.attack_buff_side()
        self.assertEqual(side["swords-dance"], "physical")
        self.assertEqual(side["dragon-dance"], "physical")
        self.assertEqual(side["nasty-plot"], "special")
        self.assertNotIn("harden", side)


class BestMove(unittest.TestCase):
    def test_the_highest_score_wins_whatever_the_kind(self):
        rows = [move_row(115, "substitute", "turret", 900), move_row(115, "tackle", "melee", 400),
                move_row(115, "water-gun", "projectile", 300)]
        self.assertEqual(picks.best_moves(rows)[115]["start"], "substitute")
        rows = [move_row(95, "tackle", "melee", 110), move_row(95, "water-gun", "projectile", 100)]
        self.assertEqual(picks.best_moves(rows)[95]["start"], "tackle")

    def test_a_move_that_dealt_nothing_loses_to_one_that_did(self):
        rows = [move_row(1, "growl", "projectile", 800, dealt=0.0), move_row(1, "vine-whip", "projectile", 5)]
        self.assertEqual(picks.best_moves(rows)[1]["start"], "vine-whip")


class BestGroup(unittest.TestCase):
    def test_any_category_and_buff_fill_is_a_candidate(self):
        self.assertTrue(picks.group_ok("water-gun+tackle+nasty-plot+harden"))
        self.assertTrue(picks.group_ok("water-gun+tackle+swords-dance+agility"))
        self.assertTrue(picks.group_ok("water-gun+hydro-pump+bubble+harden"))
        self.assertTrue(picks.group_ok("substitute+tackle+swords-dance+harden"))

    def test_owner_banned_moves_are_flagged_in_a_group(self):
        self.assertTrue(picks.has_banned("water-gun+tackle+nasty-plot+harden"))
        self.assertTrue(picks.has_banned("body-slam+whirlpool+swords-dance+harden"))
        self.assertFalse(picks.has_banned("water-gun+hyper-beam+nasty-plot+harden"))

    def test_a_group_needs_two_attacks_inside_four_slots(self):
        self.assertFalse(picks.group_ok("water-gun+nasty-plot+harden"))
        self.assertFalse(picks.group_ok("water-gun+hydro-pump+bubble+nasty-plot+harden"))

    def test_shapes(self):
        self.assertEqual(picks.shape_of("water-gun+tackle+nasty-plot+harden"), "2+atk+def")
        self.assertEqual(picks.shape_of("water-gun+hydro-pump+bubble+nasty-plot"), "3+atk")
        self.assertEqual(picks.shape_of("water-gun+hydro-pump+bubble+agility"), "3+def")

    def test_fewer_attacks_does_not_win_a_tie_on_a_lower_score(self):
        rows = [group_row(647, "water-gun+hydro-pump+nasty-plot+harden", 100),
                group_row(647, "water-gun+hydro-pump+bubble+nasty-plot", 101)]
        self.assertEqual(picks.best_groups(rows)[647]["group"], "water-gun+hydro-pump+bubble+nasty-plot")

    def test_shortlist_keeps_every_shape(self):
        rows = [group_row(647, "water-gun+hydro-pump+nasty-plot+harden", 100),
                group_row(647, "water-gun+hydro-pump+bubble+nasty-plot", 90),
                group_row(647, "water-gun+hydro-pump+bubble+harden", 80)]
        shapes = {picks.shape_of(r["group"]) for r in picks.shortlist_groups(rows, 1)[647]}
        self.assertEqual(shapes, {"2+atk+def", "3+atk", "3+def"})


if __name__ == "__main__":
    unittest.main()
