"""Per-species card order is the coin ranking of the fixed-group card bench.

The page does not print that ranking as four priorities. It prints the cards the
policy takes: the lead attack's evolution card once, when that card is not the
fill, and then the fill the bench ranked first.

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
import static_ficha  # noqa: E402
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
        self.assertIn("simulación", es.t("faq_a_cards_once", once="Imán", card="Vigor"))
        self.assertIn("simulation", en.t("faq_a_cards_once", once="Magnet", card="Vigor"))

    def test_displayed_cards_are_the_policy_picks(self) -> None:
        sim = passives.load()
        groups = {
            936: ["psychic", "heat-wave", "swords-dance", "harden"],
            150: ["psychic", "hyper-voice", "swords-dance", "harden"],
            802: ["shadow-ball", "hyper-voice", "swords-dance", "harden"],
        }
        for dex, moves in groups.items():
            ids, n_once = passives.compute(dex, moves, sim)
            stack = sim["order"][str(dex)][0]
            gate = sim["needs"].get(moves[0])
            if gate and gate != stack:
                self.assertEqual([ids, n_once], [[gate, stack], 1], dex)
            else:
                self.assertEqual([ids, n_once], [[stack], 0], dex)
            for move in moves[1:]:
                need = sim["needs"].get(move)
                if need and need not in (gate, stack):
                    self.assertNotIn(need, ids, dex)

    def test_armarouge_is_magnet_once_then_vigor(self) -> None:
        sim = passives.load()
        self.assertEqual(
            passives.compute(936, ["psychic", "heat-wave", "swords-dance", "harden"], sim),
            [["mag", "hp"], 1])
        es, en = Lang("es"), Lang("en")
        self.assertEqual(
            static_ficha.card_answer(es, ["Imán", "Vigor"], 1, False),
            "Según nuestra simulación, en este orden: Imán una vez y después Vigor.")
        self.assertEqual(
            static_ficha.card_answer(en, ["Magnet", "Vigor"], 1, False),
            "Based on our simulation, in this order: Magnet once, then Vigor.")


if __name__ == "__main__":
    unittest.main()
