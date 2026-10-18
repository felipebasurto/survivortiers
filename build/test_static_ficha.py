"""Fichas estáticas: slug, probabilidad de tirada y una página de Mewtwo ya generada.

    python3 -m unittest build/test_static_ficha.py

La página de ejemplo sale de build/render.py (site/pokemon/150-mewtwo/index.html).
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import legal  # noqa: E402
import static_ficha  # noqa: E402
from slugs import slugify, species_path  # noqa: E402

SITE = ROOT / "site"
BANNED = re.compile(
    r"\b(el|los|las|del|con|para|puesto|aguante|daño|ficha|partidas?|repeticiones|cuántos)\b",
    re.I,
)


def _visible(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(html.split())


class SlugsAndOdds(unittest.TestCase):
    def test_pull_nearest_pool(self) -> None:
        counts = {5: 1, 1: 10}
        self.assertAlmostEqual(static_ficha.pull_p(5, counts), 0.08)
        self.assertAlmostEqual(static_ficha.pull_p(1, counts), 0.092)
        self.assertEqual(static_ficha.js_round(12.5), 13)
        self.assertEqual(static_ficha.js_round(2.5), 3)

    def test_slug_matches_app_js(self) -> None:
        src = (ROOT / "src" / "app.js").read_text(encoding="utf8")
        found = re.search(r"function speciesSlug\(name\) \{([\s\S]*?)\n  \}", src)
        self.assertIsNotNone(found, "speciesSlug tiene que vivir en src/app.js")
        names = [
            "Mewtwo", "Nidoran♀", "Nidoran♂", "Farfetch'd", "Mr. Mime", "Ho-Oh",
            "Mime Jr.", "Porygon-Z", "Flabébé", "Type: Null", "Jangmo-o", "Sirfetch'd",
            "Farfetch’d",
        ]
        script = (
            "function speciesSlug(name) {" + found.group(1) + "\n}\n"
            "const names = " + json.dumps(names) + ";\n"
            "for (const n of names) console.log(speciesSlug(n));\n"
        )
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [slugify(n) for n in names])
        self.assertIn("pokemon/' + p.dex + '-' + speciesSlug", src)
        self.assertIn("pokemon/?id=", src)

    def test_published_slugs_are_unique(self) -> None:
        with (ROOT / "data" / "species_names_en.csv").open(encoding="utf8") as fh:
            names = {int(row["dex"]): row["name_en"] for row in csv.DictReader(fh)}
        pokedex = json.loads((ROOT / "data" / "pokedex_export.json").read_text(encoding="utf8"))
        paths = [species_path(p["dex"], names[p["dex"]]) for p in pokedex]
        self.assertEqual(len(paths), 966)
        self.assertEqual(len(set(paths)), 966)
        self.assertIn("150-mewtwo", paths)
        leaked = [p for p in paths if any(BANNED.fullmatch(part) for part in p.split("-"))]
        self.assertEqual(leaked, [])


class StaticMewtwo(unittest.TestCase):
    def test_sample_page_has_tier_rank_and_title_without_js(self) -> None:
        es_path = SITE / "pokemon" / "150-mewtwo" / "index.html"
        en_path = SITE / "en" / "pokemon" / "150-mewtwo" / "index.html"
        self.assertTrue(es_path.is_file(), "falta la ficha estática: python3 build/render.py")
        es, en = es_path.read_text(encoding="utf8"), en_path.read_text(encoding="utf8")
        rows = list(csv.DictReader(
            (line for line in (ROOT / "data" / "ranking_definitive.csv").read_text(encoding="utf8").splitlines()
             if not line.startswith("#"))))
        row = next(r for r in rows if r["dex"] == "150")
        stats = json.loads((ROOT / "data" / "base_stats.json").read_text(encoding="utf8"))["150"]
        species = json.loads((SITE / "data" / "species.json").read_text(encoding="utf8"))
        moves = {m["id"]: m for m in json.loads((SITE / "data" / "moves.json").read_text(encoding="utf8"))}
        ids, n_boost = species["d"]["150"][9][2], species["d"]["150"][9][5]
        game = legal.GAME_NAME
        self.assertIn(f"<title>Mewtwo en {game}: tier, build y cómo conseguirlo</title>", es)
        self.assertIn(f"<title>Mewtwo in {game}: tier, build and how to get it</title>", en)
        for html, rank_word in ((es, "puesto"), (en, "rank")):
            text = _visible(html)
            self.assertIn(row["tier"], text)
            self.assertIn(row["rank"], text)
            self.assertIn(row["rank_sim_best"], text)
            self.assertIn(row["rank_sim_start"], text)
            self.assertIn(rank_word, text.lower())
            for n in stats:
                self.assertIn(str(n), text)
            self.assertNotIn("Esta página necesita JavaScript", html)
            self.assertNotIn("This page needs JavaScript", html)
            self.assertNotIn(legal.GAME_COMMIT, html)
            self.assertIn("FAQPage", html)
            self.assertIn(f'rel="canonical" href="{legal.SITE_URL}/', html)
            self.assertIn('hreflang="es"', html)
            self.assertIn('hreflang="en"', html)
            self.assertIn('property="og:title"', html)
            self.assertIn("<h1>", html)
        buffs = ids[-n_boost:] if n_boost else []
        attacks = ids[:-n_boost] if n_boost else ids
        es_text, en_text = _visible(es), _visible(en)
        for mid in attacks + buffs:
            self.assertIn(moves[mid]["name"], es_text)
            self.assertIn(moves[mid]["en"]["name"], en_text)
        self.assertIn(f"{legal.SITE_URL}/pokemon/150-mewtwo/", es)
        self.assertIn(f"{legal.SITE_URL}/en/pokemon/150-mewtwo/", es)
        shell = (SITE / "pokemon" / "index.html").read_text(encoding="utf8")
        self.assertIn('id="slugs"', shell)
        self.assertIn("Esta página necesita JavaScript", shell)
        self.assertIn('name="robots" content="noindex"', shell)
        sitemap = (SITE / "sitemap.xml").read_text(encoding="utf8")
        self.assertEqual(sitemap.count("<url>"), (8 + 966) * 2)
        self.assertIn("/pokemon/150-mewtwo/", sitemap)
        self.assertIn("/en/pokemon/150-mewtwo/", sitemap)
        robots = (SITE / "robots.txt").read_text(encoding="utf8")
        self.assertIn(f"Sitemap: {legal.SITE_URL}/sitemap.xml", robots)


if __name__ == "__main__":
    unittest.main()
