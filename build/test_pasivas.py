"""Las cifras de la página de pasivas salen de los CSV del simulador, no se escriben a mano.

    python3 build/test_pasivas.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "build"))

import pasivas  # noqa: E402
import pasivas_rank as pr  # noqa: E402
from i18n import Lang  # noqa: E402

FIXED = ROOT / "simulator" / "results" / "fixed_group"
RANK = FIXED / "pasivas_rank_g2p2.csv"
RANK_DODGE = FIXED / "pasivas_rank_dodge_g2p2.csv"
ZIDRA = FIXED / "pasivas_zidra_g2p2.csv"
ZIDRA_DODGE = FIXED / "pasivas_zidra_dodge_g2p2.csv"
HEALS = ["0.30", "0.45", "0.55", "0.70", "1"]


def pct(path: Path, fill: str, field: str, heal: str = "0.70") -> float:
    """Igual que `pasivas_rank.py report`: mediana de la subida frente a la base sin carta ni baya."""
    by = pr.index(pr.load(path))
    base = by[("none", "", heal)]
    return 100 * median(pr.lifts(base, by[("none", fill, heal)], field))


def zidra_pct(path: Path, heal: str) -> float:
    by = pr.index(pr.load(path))
    base = by[("none", "", "")]
    return 100 * median(pr.lifts(base, by[("none", "", heal)], "median_coins"))


class RankNumbers(unittest.TestCase):
    def test_every_card_matches_the_rank_csv(self):
        for c in pasivas.CARDS:
            with self.subTest(card=c["id"]):
                self.assertEqual(round(pct(RANK, c["fill"], "median_coins"), 1), c["coin"])
                self.assertEqual(round(pct(RANK, c["fill"], "median_s"), 1), c["surv"])
                self.assertEqual(round(pct(RANK, c["fill"], "median_kpm"), 1), c["kpm"])

    def test_cards_are_ranked_by_coins(self):
        coins = [c["coin"] for c in pasivas.CARDS]
        self.assertEqual(coins, sorted(coins, reverse=True))
        # New groups spend levels on move upgrades. The median coin lift of every card is 0.
        self.assertTrue(all(c == 0 for c in coins))

    def test_dodge_scenario_keeps_the_order(self):
        coins = {c["id"]: pct(RANK_DODGE, c["fill"], "median_coins") for c in pasivas.CARDS}
        self.assertGreater(coins["rgn"], coins["hp"])
        self.assertGreater(coins["hp"], max(v for k, v in coins.items() if k not in ("rgn", "hp")))
        self.assertGreater(coins["rgn"], pct(RANK, "5", "median_coins"))


class ZidraRule(unittest.TestCase):
    def test_threshold_is_the_best_heal_in_both_scenarios(self):
        for path in (ZIDRA, ZIDRA_DODGE):
            with self.subTest(path=path.name):
                values = {h: zidra_pct(path, h) for h in HEALS}
                self.assertEqual(max(values, key=values.get), "0.70")
                self.assertGreater(values["0.70"], values["1"])

    def test_page_threshold_is_the_csv_threshold(self):
        self.assertEqual(float(HEALS[HEALS.index("0.70")]), pasivas.ZIDRA["at"])


class PageMarkup(unittest.TestCase):
    def setUp(self):
        self.es = pasivas.content(Lang("es"), "")
        self.en = pasivas.content(Lang("en"), "../")

    def test_every_card_is_a_ranked_row(self):
        for html in (self.es, self.en):
            self.assertEqual(html.count('<li class="pv-row'), len(pasivas.CARDS) + len(pasivas.COMBOS))
            self.assertEqual(html.count('<span class="pv-pos">'), len(pasivas.CARDS))

    def test_top_cards_come_before_the_zidra_callout(self):
        self.assertLess(self.es.index('class="pv-col pv-top"'), self.es.index('class="pv-box pv-zidra"'))
        self.assertLess(self.es.index('class="pv-box pv-zidra"'), self.es.index('class="pv-col pv-rest"'))

    def test_no_placeholder_is_left_unrendered(self):
        for html in (self.es, self.en):
            self.assertIsNone(re.search(r"\{\w+\}", html))

    def test_method_link_points_to_the_language_root(self):
        self.assertIn('href="metodo.html"', self.es)
        self.assertIn('href="../metodo.html"', self.en)

    def test_spanish_percentages_use_a_non_breaking_space(self):
        self.assertIn("70\u00a0%", self.es)
        self.assertNotIn("70 %", self.es)
        self.assertIn("70%", self.en)


if __name__ == "__main__":
    unittest.main()
