"""Categoría física, especial o de estado y el potenciador nuevo, frente a js/data/moves.js del juego.

    python3 -m unittest build/test_game_moves.py

Con POKESURVIVOR_DIR apuntando a una copia del repositorio del juego, también compara la lista física con
js/data/moves.js. Sin esa variable, esa comparación se salta.
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

import game_moves  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "build" / "out"


def _ranked_ids() -> dict[str, str]:
    with (DATA / "move_tierlist_v4.csv").open(encoding="utf8", newline="") as f:
        rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    return {r["move_id"]: r["kind"] for r in rows}


class DamageClassTests(unittest.TestCase):
    def test_physical_list_is_unique_and_complete(self):
        self.assertEqual(len(game_moves.PHYSICAL), 24)

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

    def test_physical_ids_are_all_known_moves(self):
        known = set(_ranked_ids()) | {u["id"] for u in game_moves.UNRANKED}
        self.assertEqual(sorted(game_moves.PHYSICAL - known), [])

    @unittest.skipUnless(os.environ.get("POKESURVIVOR_DIR"), "POKESURVIVOR_DIR no está definido")
    def test_physical_list_matches_game_source(self):
        text = (Path(os.environ["POKESURVIVOR_DIR"]) / "js" / "data" / "moves.js").read_text(encoding="utf8")
        block = re.search(r"PHYSICAL = new Set\(\[(.*?)\]\)", text, re.S).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'", block)), set(game_moves.PHYSICAL))


class UnrankedTests(unittest.TestCase):
    def test_maquinacion_numbers_match_game_entry(self):
        (nasty,) = [u for u in game_moves.UNRANKED if u["id"] == "nasty-plot"]
        self.assertEqual(nasty["stat"][1], "special attack")
        self.assertEqual(nasty["amount"], 0.13)
        self.assertEqual(nasty["stacks"], 5)
        self.assertEqual(nasty["dur"], 7)
        self.assertEqual(nasty["cd"], 0.85)
        self.assertEqual(nasty["kind"], "buff")

    def test_danzas_and_maquinacion_have_notes(self):
        for mid in ("swords-dance", "dragon-dance"):
            self.assertIn(mid, game_moves.NOTES)
        self.assertTrue(all(game_moves.NOTES[m][0] and game_moves.NOTES[m][1] for m in game_moves.NOTES))
        self.assertTrue(all(u["note"][0] and u["note"][1] for u in game_moves.UNRANKED))


class BuildOutputTests(unittest.TestCase):
    def setUp(self):
        if not (OUT / "moves.json").exists():
            self.skipTest("build/out no existe (ejecuta build/catalog.py)")

    def test_every_move_has_damage_class(self):
        moves = json.loads((OUT / "moves.json").read_text(encoding="utf8"))
        self.assertEqual(len(moves), 64)
        for m in moves:
            self.assertIn(m["damage"], game_moves.DAMAGE_CLASSES, m["id"])
            self.assertEqual(m["damage"] == "status", m["kind"] == "buff", m["id"])

    def test_unranked_has_no_tier_or_score(self):
        unranked = json.loads((OUT / "moves_unranked.json").read_text(encoding="utf8"))
        self.assertEqual([u["id"] for u in unranked], ["nasty-plot"])
        self.assertNotIn("tier", unranked[0])
        self.assertNotIn("score", unranked[0])
        self.assertEqual(unranked[0]["buff"]["cover"], 100)


if __name__ == "__main__":
    unittest.main()
