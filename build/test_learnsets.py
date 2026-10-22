"""Naturalezas y lista de MT por especie, desde simulator/data/game.json.

    uv run --python 3.12 python -m unittest discover -s build -p "test_learnsets.py"
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import i18n  # noqa: E402
import learnsets  # noqa: E402


def lang(code: str) -> i18n.Lang:
    return i18n.Lang(code)


class NaturalezasTest(unittest.TestCase):
    def test_one_row_per_nature_and_neutrals_do_not_change(self) -> None:
        for code in ("es", "en"):
            L = lang(code)
            rows = learnsets.nature_rows(L)
            self.assertEqual(len(rows), 25, code)
            neutral = L.t("nat_neutral")
            for name, up, down in rows:
                self.assertTrue(name, code)
                self.assertEqual(up == neutral, down == neutral, (name, up, down))

    def test_page_marks_up_and_down_cells(self) -> None:
        html = learnsets.naturalezas_content(lang("es"))
        self.assertEqual(html.count('class="nat-up"'), 20)
        self.assertEqual(html.count('class="nat-down"'), 20)
        self.assertEqual(html.count('class="nat-neutral"'), 10)


class TmTest(unittest.TestCase):
    def test_species_list_matches_game_data(self) -> None:
        dex = learnsets.GAME["dex"][0]
        html = learnsets.tm_section(lang("es"), dex["dex"], {})
        self.assertEqual(html.count('<li>'), len(dex["tms"]))

    def test_species_without_tms_renders_nothing(self) -> None:
        bare = [d["dex"] for d in learnsets.GAME["dex"] if not d.get("tms")]
        if not bare:
            self.skipTest("todas las especies tienen MT")
        self.assertEqual(learnsets.tm_section(lang("es"), bare[0], {}), "")

    def test_english_move_name_falls_back_to_spanish(self) -> None:
        L = lang("en")
        self.assertEqual(learnsets._move_name(L, "xx-unknown", {}), "Xx Unknown")
        self.assertEqual(learnsets._move_name(L, "xx", {"xx": {"name": "Ataque"}}), "Ataque")


if __name__ == "__main__":
    unittest.main()
