"""Builds cuerpo a cuerpo y a distancia (build/builds.py) y su texto en la ficha.

    python3 -m unittest build/test_builds.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import builds  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402


def _sample_dex(n: int = 1) -> list[int]:
    """Especies que tienen build cuerpo a cuerpo y a distancia."""
    return [d for d, groups in builds.space().items() if {"melee", "ranged"} <= set(groups.values())][:n]


class Candidates(unittest.TestCase):
    def test_every_candidate_meets_the_rules(self) -> None:
        for dex in sorted(builds.space())[:60]:
            for group, build in builds.candidates(dex).items():
                with self.subTest(dex=dex, group=group):
                    self.assertEqual(builds.violations(dex, build, group), [])

    def test_attack_buff_raises_an_attack_of_the_group(self) -> None:
        self.assertEqual(builds.attack_buffs(["ember", "flamethrower"]), ["nasty-plot"])
        self.assertEqual(builds.attack_buffs(["ember", "meteor-mash"], dragon_dance=False), ["nasty-plot", "swords-dance"])

    def test_every_shape_fills_the_four_slots(self) -> None:
        for group in builds.variants(["ember", "meteor-mash", "rock-throw"]) + builds.variants(["ember", "meteor-mash"]):
            self.assertEqual(len(group.split("+")), builds.picks.BOND_SLOTS, group)


class Violations(unittest.TestCase):
    def test_melee_build_without_melee_move_is_reported(self) -> None:
        dex = _sample_dex()[0]
        group = next(g for g, b in builds.candidates(dex).items() if b == "ranged")
        self.assertTrue(builds.violations(dex, "melee", group))

    def test_ranged_build_with_melee_move_is_reported(self) -> None:
        dex = _sample_dex()[0]
        group = next(g for g, b in builds.candidates(dex).items() if b == "melee")
        self.assertTrue(builds.violations(dex, "ranged", group))


class Moves(unittest.TestCase):
    def test_build_moves_puts_boosts_last(self) -> None:
        moves, n = builds.build_moves("hyper-beam+poison-sting+sludge+swords-dance")
        self.assertEqual(moves, ["hyper-beam", "poison-sting", "sludge", "swords-dance"])
        self.assertEqual(n, 1)
        moves, n = builds.build_moves("sludge+seed-bomb+nasty-plot+harden")
        self.assertEqual(moves, ["sludge", "seed-bomb", "nasty-plot", "harden"])
        self.assertEqual(n, 2)


class Text(unittest.TestCase):
    def _b(self, score: float) -> dict:
        return {"score": score}

    def test_winner_and_tie(self) -> None:
        self.assertEqual(static_ficha._winner({"melee": self._b(50), "ranged": self._b(40)}), "melee")
        self.assertEqual(static_ficha._winner({"melee": self._b(40), "ranged": self._b(50)}), "ranged")
        self.assertIsNone(static_ficha._winner({"melee": self._b(45), "ranged": self._b(45)}))
        self.assertEqual(static_ficha._winner({"melee": None, "ranged": self._b(45)}), "ranged")
        self.assertIsNone(static_ficha._winner({"melee": None, "ranged": None}))

    def test_small_gap_says_so_plainly(self) -> None:
        win, low = self._b(100.0), self._b(98.0)
        text = static_ficha._verdict(ES, "ranged", low, win, "melee")
        self.assertIn("Solo un 2\u00a0% peor que la build cuerpo a cuerpo.", text)
        text_en = static_ficha._verdict(EN, "ranged", low, win, "melee")
        self.assertIn("Only 2% below the melee build.", text_en)

    def test_large_gap_drops_the_adverb(self) -> None:
        win, low = self._b(100.0), self._b(70.0)
        self.assertIn("Un 30\u00a0% peor que la build cuerpo a cuerpo.", static_ficha._verdict(ES, "ranged", low, win, "melee"))

    def test_winner_is_marked_and_missing_other_is_silent(self) -> None:
        win = self._b(100.0)
        self.assertIn("is-best", static_ficha._verdict(ES, "melee", win, self._b(90.0), "melee"))
        self.assertEqual(static_ficha._verdict(ES, "melee", win, None, "melee"), "")

    def test_missing_build_renders_the_none_line(self) -> None:
        empty = static_ficha._build_option(ES, {}, {}, "ranged", None, None, None)
        self.assertIn("No hay ataques a distancia que le valgan.", empty)
        self.assertIn("is-none", empty)


if __name__ == "__main__":
    unittest.main()
