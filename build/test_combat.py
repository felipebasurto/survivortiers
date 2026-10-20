"""Ataque y defensa del juego: clasificación del lado fuerte, datos importados y bloque de la ficha.

    python3 -m unittest build/test_combat.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import catalog  # noqa: E402
import import_game_combat  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402


class AttackKindTest(unittest.TestCase):
    def test_sides(self) -> None:
        self.assertEqual(catalog.attack_kind(1.16, 1.3), "spec")
        self.assertEqual(catalog.attack_kind(1.3, 1.16), "phys")

    def test_mixed_within_five_hundredths_inclusive(self) -> None:
        self.assertEqual(catalog.attack_kind(1.0, 0.95), "mix")
        self.assertEqual(catalog.attack_kind(1.10, 1.05), "mix")
        self.assertEqual(catalog.attack_kind(1.05, 1.10), "mix")
        self.assertEqual(catalog.attack_kind(1.11, 1.05), "phys")

    def test_group_side_uses_move_damage_class(self) -> None:
        self.assertEqual(catalog.group_side(["tackle", "quick-attack"]), "phys")
        self.assertEqual(catalog.group_side(["ember", "flamethrower"]), "spec")
        self.assertEqual(catalog.group_side(["tackle", "ember"]), "mix")

    def test_group_side_refuses_a_boost(self) -> None:
        with self.assertRaises(catalog.CatalogError):
            catalog.group_side(["swords-dance"])
        with self.assertRaises(catalog.CatalogError):
            catalog.group_side([])


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
            for k in catalog.COMBAT_KEYS:
                self.assertIn(k, p, p["dex"])
            self.assertLessEqual(abs(p["atk"] - max(p["pa"], p["sa"])), 0.005, p["dex"])


class StaticBlockTest(unittest.TestCase):
    def entry(self, pa: float, sa: float, df: int, sd: int) -> dict:
        return {"dex": 6, "name": "Charizard", "nameEn": "Charizard", "base": {"pa": pa, "sa": sa, "df": df, "sd": sd}}

    def test_block_in_spanish(self) -> None:
        html = static_ficha.combat(ES, self.entry(1.16, 1.3, 78, 85))
        self.assertIn('data-kind="spec"', html)
        self.assertIn("Atacante especial", html)
        self.assertIn("×1,16", html)
        self.assertIn("×1,30", html)
        self.assertIn(">78<", html)
        self.assertIn(">85<", html)
        self.assertIn("hasta un 22\u00a0% menos", html)
        self.assertIn("hasta un 25\u00a0% más", html)
        self.assertIn("5a23d49", html)

    def test_block_in_english_and_mixed_label(self) -> None:
        html = static_ficha.combat(EN, self.entry(1.0, 1.02, 40, 120))
        self.assertIn('data-kind="mix"', html)
        self.assertIn("Mixed", html)
        self.assertIn("×1.02", html)
        self.assertIn("up to 22\u00a0% and low defense adds up to 25\u00a0%", html)


if __name__ == "__main__":
    unittest.main()
