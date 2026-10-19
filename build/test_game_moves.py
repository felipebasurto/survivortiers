"""Categoría física, especial o de estado y los potenciadores, frente a js/data/moves.js del juego.

    python3 -m unittest build/test_game_moves.py

Con POKESURVIVOR_DIR apuntando a una copia del repositorio del juego, también compara la lista física de
data/game_stats.json con js/data/moves.js. Sin esa variable, esa comparación se salta.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import sitefixture  # noqa: E402
import catalog  # noqa: E402
import game_moves  # noqa: E402
import gamestats  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "build" / "out"


def _ranked_ids() -> dict[str, str]:
    with (DATA / "move_tierlist_v4.csv").open(encoding="utf8", newline="") as f:
        rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    return {r["move_id"]: r["kind"] for r in rows}


class DamageClassTests(unittest.TestCase):
    def test_physical_list_is_complete(self):
        self.assertEqual(len(game_moves.physical_ids()), 41)

    def test_every_ranked_move_gets_a_class(self):
        for mid, kind in _ranked_ids().items():
            self.assertIn(game_moves.damage_class(mid, kind), game_moves.DAMAGE_CLASSES, mid)

    def test_buffs_are_status_even_with_physical_id(self):
        self.assertEqual(game_moves.damage_class("swords-dance", "buff"), "status")
        self.assertEqual(game_moves.damage_class("dragon-dance", "buff"), "status")

    def test_physical_and_special_examples(self):
        self.assertEqual(game_moves.damage_class("tackle", "melee"), "physical")
        self.assertEqual(game_moves.damage_class("flame-wheel", "orbit"), "physical")
        self.assertEqual(game_moves.damage_class("ember", "projectile"), "special")
        self.assertEqual(game_moves.damage_class("flamethrower", "cone"), "special")

    def test_physical_ids_are_all_ranked_attacks(self):
        self.assertEqual(sorted(game_moves.physical_ids() - set(_ranked_ids())), [])

    def test_tier_list_is_every_attack_and_no_boost(self):
        game = json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))["moves"]
        attacks = {mid for mid, m in game.items() if m["kind"] != "buff"}
        self.assertEqual(set(_ranked_ids()), attacks)

    def test_only_the_melee_kind_is_close_range(self):
        with (DATA / "move_tierlist_v4.csv").open(encoding="utf8", newline="") as f:
            for r in csv.DictReader(line for line in f if not line.startswith("#")):
                self.assertEqual(r["category"] == "cuerpo a cuerpo", r["kind"] == "melee", r["move_id"])

    @unittest.skipUnless(os.environ.get("POKESURVIVOR_DIR"), "POKESURVIVOR_DIR no está definido")
    def test_physical_list_matches_game_source(self):
        text = (Path(os.environ["POKESURVIVOR_DIR"]) / "js" / "data" / "moves.js").read_text(encoding="utf8")
        block = re.search(r"PHYSICAL = new Set\(\[(.*?)\]\)", text, re.S).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'", block)), set(game_moves.physical_ids()))


class BoostTests(unittest.TestCase):
    def test_every_game_boost_is_listed_with_game_numbers(self):
        game = json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))["moves"]
        boosts = catalog.load_unranked()
        self.assertEqual([b["id"] for b in boosts], list(gamestats.BOOST_ORDER))
        self.assertEqual({b["id"] for b in boosts}, {mid for mid, m in game.items() if m["kind"] == "buff"})
        for b in boosts:
            g = game[b["id"]]["buff"]
            for k in ("stat", "amount", "stacks", "dur", "cd", "max"):
                self.assertEqual(b["buff"][k], g[k], (b["id"], k))
            self.assertEqual(b["damage"], "status")

    def test_max_level_follows_the_buff_ladder(self):
        # moves.js LADDERS.buff: +1 stack, ×1.4 amount, ×1.5 duration, +1 stack and ×1.4 amount.
        for mid in gamestats.BOOST_ORDER:
            b = gamestats.move(mid)["buff"]
            top = b["max"]
            self.assertEqual(top["level"], 5, mid)
            self.assertEqual(top["stacks"], b["stacks"] + 2, mid)
            self.assertAlmostEqual(top["amount"], b["amount"] * 1.4 * 1.4, places=4, msg=mid)
            self.assertAlmostEqual(top["dur"], b["dur"] * 1.5, places=4, msg=mid)
            self.assertEqual(top["cd"], b["cd"], mid)

    @unittest.skipUnless(os.environ.get("POKESURVIVOR_DIR"), "POKESURVIVOR_DIR no está definido")
    def test_buff_ladder_matches_game_source(self):
        text = (Path(os.environ["POKESURVIVOR_DIR"]) / "js" / "data" / "moves.js").read_text(encoding="utf8")
        block = re.search(r"\n    buff: \[(.*?)\n    \]", text, re.S).group(1)
        self.assertEqual(re.findall(r"m: (\{[^}]*\})", block),
                         ["{ stacks: 1 }", "{ amount: 1.40 }", "{ dur: 1.50 }", "{ stacks: 1, amount: 1.40 }"])

    def test_attack_boosts_have_notes(self):
        for mid in ("swords-dance", "dragon-dance", "nasty-plot"):
            self.assertIn(mid, game_moves.NOTES)
        self.assertTrue(all(game_moves.NOTES[m][0] and game_moves.NOTES[m][1] for m in game_moves.NOTES))


class BuildOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site(need_site=False)

    def setUp(self):
        if not (OUT / "moves.json").exists():
            self.skipTest("build/out no existe (ejecuta build/catalog.py)")

    def test_every_move_has_damage_class(self):
        moves = json.loads((OUT / "moves.json").read_text(encoding="utf8"))
        game = json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))["moves"]
        self.assertEqual(len(moves), len(game) - len(gamestats.BOOST_ORDER))
        for m in moves:
            self.assertIn(m["damage"], ("physical", "special"), m["id"])
            self.assertNotEqual(m["kind"], "buff", m["id"])

    def test_boosts_have_no_tier_or_score(self):
        unranked = json.loads((OUT / "moves_unranked.json").read_text(encoding="utf8"))
        self.assertEqual([u["id"] for u in unranked], list(gamestats.BOOST_ORDER))
        for u in unranked:
            self.assertNotIn("tier", u)
            self.assertNotIn("score", u)
            self.assertEqual(u["buff"]["cover"], 100, u["id"])


if __name__ == "__main__":
    unittest.main()
