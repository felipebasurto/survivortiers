"""Per-species card order is the coin ranking of the fixed-group card bench.

The page shows all eight stat cards in that order, best first (passives.priority), and marks the card the lead
attack needs to evolve. compute() is the policy's own pick sequence and feeds the summaries, which stay as they are.

    python3 build/test_card_priority.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "build"))

import passives  # noqa: E402
import static_ficha  # noqa: E402
from i18n import Lang  # noqa: E402

STATS = ["atk", "spd", "hp", "def", "cd", "rgn", "mag", "xp"]
GARCHOMP_GROUP = ["bonemerang", "dragon-rage", "dragon-dance", "harden"]


class CardOrder(unittest.TestCase):
    def test_faq_templates_cite_the_simulation(self) -> None:
        es, en = Lang("es"), Lang("en")
        self.assertIn("simulación", es.t("faq_a_cards", cards="Vigor"))
        self.assertIn("simulation", en.t("faq_a_cards", cards="Vigor"))
        self.assertIn("simulación", es.t("faq_a_cards_gate", cards="Vigor", once="Imán"))
        self.assertIn("simulation", en.t("faq_a_cards_gate", cards="Vigor", once="Magnet"))

    def test_priority_is_the_species_order_in_full(self) -> None:
        sim = passives.load()
        for dex, order in sim["order"].items():
            ids, gate = passives.priority(int(dex), [], sim)
            self.assertEqual(ids, order, dex)
            self.assertIsNone(gate, dex)

    def test_gate_is_the_card_the_lead_attack_needs(self) -> None:
        sim = passives.load()
        ids, gate = passives.priority(445, GARCHOMP_GROUP, sim)
        self.assertEqual(gate, "atk")
        self.assertEqual(ids, ["rgn", "spd", "xp", "def", "hp", "atk", "mag", "cd"])

    def test_every_needed_card_is_a_gate_for_its_move(self) -> None:
        sim = passives.load()
        self.assertEqual(len(sim["needs"]), 97)
        for move, card in sim["needs"].items():
            self.assertEqual(passives.priority(1, [move], sim)[1], card, move)
        # 19 Oct 2026 moves (moves.js EVO, vendored at 5a23d49).
        self.assertEqual(sim["needs"]["hyper-beam"], "atk")
        self.assertEqual(sim["needs"]["ominous-wind"], "mag")
        self.assertEqual(sim["needs"]["outrage"], "hp")
        self.assertIsNone(passives.priority(1, ["no-such-move"], sim)[1])

    def test_priority_refuses_an_incomplete_order(self) -> None:
        sim = {"order": {"1": ["atk", "spd"]}, "needs": {}}
        with self.assertRaises(ValueError):
            passives.priority(1, [], sim)

    def test_summary_facts_keep_the_policy_picks(self) -> None:
        sim = passives.load()
        shown = passives.compute(936, ["psychic", "heat-wave", "swords-dance", "harden"], sim)
        # psychic evolves on Imán; the policy takes that card once, then stacks the best coin card.
        self.assertEqual(shown, [["mag", "rgn"], 1])

    def test_card_answer_names_the_gate_once(self) -> None:
        es, en = Lang("es"), Lang("en")
        self.assertEqual(
            static_ficha.card_answer(es, ["Síntesis", "Potencia"], "Potencia"),
            "Según nuestra simulación, en este orden: Síntesis y Potencia. Potencia solo hace falta una vez, "
            "para evolucionar el ataque.")
        self.assertEqual(
            static_ficha.card_answer(en, ["Synthesis", "Power"], None),
            "Based on our simulation, in this order: Synthesis and Power.")


if __name__ == "__main__":
    unittest.main()
