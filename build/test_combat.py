"""Ataque y defensa del juego importados del código (build/import_game_combat.py).

    python3 -m unittest build/test_combat.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import import_game_combat  # noqa: E402


class ImportTest(unittest.TestCase):
    def test_merge_inserts_combat_after_atk_and_keeps_rest(self) -> None:
        export = [{"dex": 6, "name": "Charizard", "types": ["fire", "flying"], "gen": 1, "rarity": 4,
                   "hp": 105, "spd": 120, "atk": 1.3, "starter": False}]
        game = [{"dex": 6, "name": "Charizard", "types": ["fire", "flying"], "gen": 1, "rarity": 4,
                 "hp": 105, "spd": 120, "atk": 1.3, "pa": 1.16, "sa": 1.3, "df": 78, "sd": 85, "starter": False}]
        (row,) = import_game_combat.merge(export, game)
        self.assertEqual(list(row)[list(row).index("atk") + 1:list(row).index("atk") + 5], ["pa", "sa", "df", "sd"])
        self.assertEqual((row["pa"], row["sa"], row["df"], row["sd"]), (1.16, 1.3, 78, 85))
        self.assertFalse(row["starter"])

    def test_merge_refuses_a_changed_base_stat(self) -> None:
        export = [{"dex": 6, "name": "Charizard", "types": ["fire"], "gen": 1, "rarity": 4, "hp": 100, "spd": 120,
                   "atk": 1.3}]
        game = [{"dex": 6, "name": "Charizard", "types": ["fire"], "gen": 1, "rarity": 4, "hp": 105, "spd": 120,
                 "atk": 1.3, "pa": 1.16, "sa": 1.3, "df": 78, "sd": 85}]
        with self.assertRaises(import_game_combat.ImportFailure):
            import_game_combat.merge(export, game)

    def test_export_has_combat_fields_for_all_species(self) -> None:
        export = json.loads((ROOT / "data" / "pokedex_export.json").read_text(encoding="utf8"))
        self.assertEqual(len(export), 966)
        for p in export:
            for k in ("pa", "sa", "df", "sd"):
                self.assertIn(k, p, p["dex"])
            self.assertLessEqual(abs(p["atk"] - max(p["pa"], p["sa"])), 0.005, p["dex"])


if __name__ == "__main__":
    unittest.main()
