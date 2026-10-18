"""Pruebas del buscador por tipos y del planificador de build. Las matemáticas están en src/tools.js: aquí se le pasan
los datos reales (data/game_stats.json, build/out/public/) a test_tools.js con Node, y se comprueban los datos y el HTML
que salen de Python.

    python3 -m unittest build/test_tools.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import finder  # noqa: E402
import gamestats  # noqa: E402
import pasivas  # noqa: E402
import planner  # noqa: E402
import repertorio  # noqa: E402
import slugs  # noqa: E402
import toolpages  # noqa: E402
from i18n import EN, ES  # noqa: E402

OUT_PUBLIC = ROOT / "build" / "out" / "public"


class ToolsDataTest(unittest.TestCase):
    def test_boost_order_lists_every_boost(self):
        buffs = {mid for mid, m in gamestats.GAME["moves"].items() if "buff" in m}
        self.assertEqual(set(gamestats.BOOST_ORDER), buffs)

    def test_dances_and_machination_split_by_stat(self):
        self.assertEqual(gamestats.move("swords-dance")["buff"]["stat"], "patk")
        self.assertEqual(gamestats.move("dragon-dance")["buff"]["stat"], "patk")
        self.assertEqual(gamestats.move("nasty-plot")["buff"]["stat"], "satk")
        for mid in gamestats.DANCE_IDS:
            self.assertIsNone(gamestats.cat(mid))

    def test_every_attack_has_one_category(self):
        for mid, m in gamestats.GAME["moves"].items():
            if "buff" in m:
                self.assertIsNone(m["cat"], mid)
            else:
                self.assertIn(m["cat"], ("physical", "special"), mid)

    def test_game_commit_is_pinned(self):
        self.assertRegex(gamestats.COMMIT, r"^[0-9a-f]{7,40}$")
        self.assertIn(gamestats.COMMIT, gamestats.game_url("js/data/moves.js"))

    def test_side_matches_stats_rule(self):
        for dex, (pa, sa, _, _) in ((int(k), v) for k, v in gamestats.GAME["dex"].items()):
            self.assertEqual(gamestats.side_of(dex), "special" if sa > pa else "physical")

    def test_site_json_shape(self):
        js = gamestats.site_json()
        self.assertEqual(set(js), {"commit", "chart", "moves", "pool", "dex"})
        self.assertEqual(len(js["chart"]), 18)
        self.assertEqual(js["moves"]["swords-dance"]["b"]["stat"], "patk")
        self.assertIn("i", js["moves"]["nasty-plot"])


class ToolsNodeTest(unittest.TestCase):
    def test_pure_functions_against_real_data(self):
        if shutil.which("node") is None:
            self.skipTest("node no está instalado")
        if not (OUT_PUBLIC / "species.json").exists():
            self.skipTest("falta build/out/: ejecuta antes python3 build/catalog.py")
        index = json.loads((OUT_PUBLIC / "pokemon-index.json").read_text(encoding="utf8"))
        species = json.loads((OUT_PUBLIC / "species.json").read_text(encoding="utf8"))
        bundle = {
            "game": json.loads(json.dumps(gamestats.site_json())),
            "species": species,
            "index": index,
            "matrix": gamestats.TYPE_MATRIX,
            "slugs": {str(p["dex"]): slugs.species_path(p["dex"], p["nameEn"]) for p in index},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf8")
            res = subprocess.run(["node", str(HERE / "test_tools.js"), str(path)], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


class ToolsHtmlTest(unittest.TestCase):
    def test_repertorio_box_in_both_languages(self):
        for L, title in ((ES, "Antes de comprar el Repertorio"), (EN, "Before you buy Repertoire")):
            html = repertorio.box(L)
            self.assertIn('class="rep-warn"', html)
            self.assertIn(title, html)
            self.assertEqual(html.count("<li>"), 3)

    def test_boost_table_uses_game_values(self):
        html = pasivas._boosts(ES, "../")
        self.assertIn('id="potenciadores"', html)
        self.assertIn("Danza Espada", html)
        self.assertIn("+13\u00a0%", html)
        self.assertIn(gamestats.COMMIT, html)

    def test_tool_folders_match_between_languages(self):
        self.assertEqual(toolpages.twin(ES, "finder"), "type-finder/index.html")
        self.assertEqual(toolpages.twin(EN, "planner"), "planificador-build/index.html")
        self.assertEqual(toolpages.target(ES, "@finder"), "buscador-tipos/")
        self.assertEqual(toolpages.target(EN, "@planner"), "build-planner/")
        self.assertEqual(toolpages.target(ES, "index.html"), "index.html")

    def test_finder_page_has_both_tool_roots(self):
        html = finder.content(ES)
        self.assertIn('id="tf-app"', html)
        self.assertIn('id="tf-list"', html)
        self.assertIn('id="i18n"', html)
        self.assertIn('class="tf-table"', html)

    def test_planner_page_has_targets_for_script(self):
        html = planner.content(EN)
        for hook in ('id="bp-app"', 'id="bp-q"', 'id="bp-slots"', 'id="bp-item"', 'id="bp-cards"', 'id="bp-warn"',
                     'id="bp-result"', 'id="bp-boostcount"', 'id="bp-list"'):
            self.assertIn(hook, html)
        self.assertIn('id="bp-app" hidden', html)


if __name__ == "__main__":
    unittest.main()
