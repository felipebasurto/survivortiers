"""Lista de Pokémon con shiny y sus sprites. python3 -m unittest build/test_shiny_sprites.py"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shiny_sprites as ss  # noqa: E402
META = """/* cabecera */
G.SPRITE_META = {
  1: {"s":1,"a":{"Idle":{"w":32,"h":40}},"sh":1},
  2: {"s":1,"a":{"Idle":{"w":32,"h":40}}},
  3: {"s":1,"a":{"Idle":{"w":40,"h":40}},"sa":{"Idle":{"w":48,"h":40}},"sh":1},
};
"""


class ParseMeta(unittest.TestCase):
    def test_entries_and_shiny_flag(self) -> None:
        meta = ss.parse_meta(META)
        self.assertEqual(sorted(meta), [1, 2, 3])
        self.assertEqual(ss.shiny_dex(meta), [1, 3])

    def test_shiny_geometry_overrides_idle_only_for_shiny(self) -> None:
        meta = ss.parse_meta(META)
        self.assertEqual(ss.idle_size(meta[3], shiny=False), {"w": 40, "h": 40})
        self.assertEqual(ss.idle_size(meta[3], shiny=True), {"w": 48, "h": 40})
        self.assertEqual(ss.idle_size(meta[1], shiny=True), {"w": 32, "h": 40})

    def test_rejects_file_without_entries(self) -> None:
        with self.assertRaises(ss.ShinyError):
            ss.parse_meta("G.SPRITE_META = {};\n")


class Repo(unittest.TestCase):
    def test_vendored_list_matches_sprites(self) -> None:
        self.assertEqual(ss.main([]), 0)

    def test_vendored_list_comes_from_pinned_commit(self) -> None:
        doc = json.loads((ROOT / "data" / "shiny_species.json").read_text(encoding="utf8"))
        self.assertEqual(doc["source"]["commit"], ss.COMMIT)
        self.assertEqual(doc["count"], 958)
        self.assertEqual(sorted(doc["withoutShiny"]), [588, 820, 847, 868, 896, 916, 933, 1007])


if __name__ == "__main__":
    unittest.main()
