"""Owner rules and the pick functions, on small synthetic tables.

    python3 build/test_picks.py
"""
from __future__ import annotations

import unittest

import owner_rules
import picks


def move_row(dex, start, kind, score, dealt=100.0, kills=10.0):
    return {"dex": str(dex), "start": start, "kind": kind, "median_score": str(score), "median_s": "600",
            "mean_score": str(score), "median_dealt": str(dealt), "median_kills": str(kills)}


def group_row(dex, group, score, kills=10.0):
    return {"dex": str(dex), "group": group, "median_score": str(score), "median_s": "600",
            "mean_score": str(score), "median_dealt": "100", "median_kills": str(kills)}


class OwnerRules(unittest.TestCase):
    def test_sustituto_is_not_an_attack(self):
        self.assertFalse(owner_rules.is_attack("substitute", "turret", 500.0))
        self.assertTrue(owner_rules.is_attack("shadow-ball", "projectile", 500.0))

    def test_buffs_and_zero_damage_are_not_attacks(self):
        self.assertFalse(owner_rules.is_attack("swords-dance", "buff"))
        self.assertFalse(owner_rules.is_attack("water-gun", "projectile", 0.0))

    def test_only_gengar_loses_melee(self):
        self.assertFalse(owner_rules.allows_melee(94))
        self.assertTrue(owner_rules.allows_melee(95))

    def test_melee_takes_the_penalty(self):
        self.assertAlmostEqual(owner_rules.adjusted(100.0, True), 100.0 * owner_rules.MELEE_SCORE_FACTOR)
        self.assertEqual(owner_rules.adjusted(100.0, False), 100.0)


class BestMove(unittest.TestCase):
    def test_sustituto_never_wins(self):
        rows = [move_row(115, "substitute", "turret", 900), move_row(115, "tackle", "melee", 400),
                move_row(115, "water-gun", "projectile", 300)]
        self.assertEqual(picks.best_moves(rows)[115]["start"], "tackle")

    def test_melee_penalty_can_flip_the_winner(self):
        rows = [move_row(95, "tackle", "melee", 110), move_row(95, "water-gun", "projectile", 100)]
        self.assertEqual(picks.best_moves(rows)[95]["start"], "water-gun")

    def test_gengar_never_gets_melee(self):
        rows = [move_row(94, "lick", "melee", 900), move_row(94, "shadow-ball", "projectile", 100)]
        self.assertEqual(picks.best_moves(rows)[94]["start"], "shadow-ball")

    def test_a_move_that_dealt_nothing_loses_to_one_that_did(self):
        rows = [move_row(1, "growl", "projectile", 800, dealt=0.0), move_row(1, "vine-whip", "projectile", 5)]
        self.assertEqual(picks.best_moves(rows)[1]["start"], "vine-whip")


class BestGroup(unittest.TestCase):
    def test_mixed_categories_are_rejected(self):
        self.assertFalse(picks.group_ok(647, "water-gun+tackle+nasty-plot+harden"))

    def test_buff_must_match_category(self):
        self.assertTrue(picks.group_ok(647, "water-gun+hydro-pump+nasty-plot+harden"))
        self.assertFalse(picks.group_ok(647, "water-gun+hydro-pump+swords-dance+harden"))

    def test_sustituto_group_is_rejected(self):
        self.assertFalse(picks.group_ok(115, "substitute+tackle+swords-dance+harden"))

    def test_buff_is_required(self):
        self.assertFalse(picks.group_ok(647, "water-gun+hydro-pump+harden"))

    def test_fewer_attacks_does_not_win_a_tie_on_a_lower_score(self):
        rows = [group_row(647, "water-gun+hydro-pump+nasty-plot+harden", 100),
                group_row(647, "water-gun+hydro-pump+bubble+nasty-plot", 101)]
        self.assertEqual(picks.best_groups(rows)[647]["group"], "water-gun+hydro-pump+bubble+nasty-plot")

    def test_shortlist_keeps_both_shapes(self):
        rows = [group_row(647, "water-gun+hydro-pump+nasty-plot+harden", 100),
                group_row(647, "water-gun+hydro-pump+bubble+nasty-plot", 90)]
        shapes = {r["group"] for r in picks.shortlist_groups(rows, 1)[647]}
        self.assertEqual(len(shapes), 2)


if __name__ == "__main__":
    unittest.main()
