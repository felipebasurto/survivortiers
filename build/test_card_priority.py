"""Per-species card order is the coin ranking of the fixed-group card bench.

    python3 build/test_card_priority.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "build"))

import card_priority  # noqa: E402
import passives  # noqa: E402
from i18n import Lang  # noqa: E402

COINS = ROOT / "simulator" / "results" / "fixed_group" / "passives_coins_g2p2.csv"
STATS = ["atk", "spd", "hp", "def", "cd", "rgn", "mag", "xp"]


class CardOrder(unittest.TestCase):
    def test_order_matches_the_coin_bench(self) -> None:
        self.assertTrue(COINS.is_file(), "falta el banco de cartas: simulator/card_priority.py")
        fresh = card_priority.orders_from(COINS)
        stored = json.loads((ROOT / "data" / "passive_sim.json").read_text(encoding="utf8"))
        self.assertEqual(set(stored["order"]), set(fresh))
        self.assertEqual(len(fresh), 966)
        for dex, order in fresh.items():
            self.assertEqual(order, stored["order"][dex], dex)
            self.assertEqual(sorted(order), sorted(STATS))

    def test_faq_template_still_cites_the_simulation(self) -> None:
        es, en = Lang("es"), Lang("en")
        self.assertIn("simulación", es.t("faq_a_cards", cards="Vigor"))
        self.assertIn("simulation", en.t("faq_a_cards", cards="Vigor"))

    def test_displayed_cards_come_from_that_order(self) -> None:
        sim = passives.load()
        shown = passives.compute(150, ["psychic", "hyper-voice"], sim)
        self.assertLessEqual(len(shown[0]), 4)
        self.assertTrue(set(shown[0]) <= set(sim["order"]["150"]) | set(sim["needs"].values()))


if __name__ == "__main__":
    unittest.main()
