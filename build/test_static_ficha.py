"""Fichas estáticas: slug, probabilidad de tirada, el porqué y una página de Mewtwo ya generada.

    python3 -m unittest build/test_static_ficha.py

La página de ejemplo sale de build/render.py (site/pokemon/150-mewtwo/index.html).
"""
from __future__ import annotations

import csv
import html as html_lib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import agents  # noqa: E402
import landing  # noqa: E402
import legal  # noqa: E402
import sitefixture  # noqa: E402
import static_ficha  # noqa: E402
import toolpages  # noqa: E402
from i18n import EN, ES  # noqa: E402
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
    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()

    def test_sample_page_has_rank_builds_why_and_stats_without_js(self) -> None:
        es_path = SITE / "pokemon" / "150-mewtwo" / "index.html"
        en_path = SITE / "en" / "pokemon" / "150-mewtwo" / "index.html"
        self.assertTrue(es_path.is_file(), "falta la ficha estática: python3 build/render.py")
        es, en = es_path.read_text(encoding="utf8"), en_path.read_text(encoding="utf8")
        row = next(r for r in csv.DictReader((SITE / "data" / "ranking.csv").read_text(encoding="utf8").splitlines())
                   if r["dex"] == "150")
        pair = json.loads((SITE / "data" / "species.json").read_text(encoding="utf8"))["builds"]["150"]
        moves = {m["id"]: m for m in json.loads((SITE / "data" / "moves.json").read_text(encoding="utf8"))}
        moves.update({m["id"]: m for m in json.loads((SITE / "data" / "moves_unranked.json").read_text(encoding="utf8"))})
        game = legal.GAME_NAME
        self.assertIn(f"<title>Mewtwo en {game}: tier {row['tier']}, mejor build y ataques | SurvivorTiers</title>", es)
        self.assertIn(f"<title>Mewtwo in {game}: {row['tier']} tier, best build and moves | SurvivorTiers</title>", en)
        self.assertEqual(row["build"], pair["best"])
        for html, why in ((es, "Por qué está en el puesto"), (en, "Why it ranks")):
            self.assertRegex(html, r"<h1>Mewtwo <")
            text = _visible(html)
            self.assertIn(f"{why} {row['rank']}", text)
            self.assertIn(f'<section class="why" id="porque"', html)
            self.assertIn(f'<section class="sheet stats" id="stats"', html)
            self.assertIn('<section class="bx" id="build"', html)
            self.assertNotIn(legal.UPDATED_COMMIT, text)
            self.assertIn("FAQPage", html)
            self.assertIn(f'rel="canonical" href="{legal.SITE_URL}/', html)
            self.assertIn('hreflang="es"', html)
            self.assertIn('hreflang="en"', html)
        shown = json.loads((ROOT / "data" / "bounded_ranking.json").read_text(encoding="utf8"))["species"]["150"]
        for b in shown.values():
            for mid in b["attacks"]:
                if mid in moves:
                    self.assertIn(moves[mid]["name"], _visible(es))
                    self.assertIn(moves[mid]["en"]["name"], _visible(en))
        shell = (SITE / "pokemon" / "index.html").read_text(encoding="utf8")
        self.assertIn('id="slugs"', shell)
        self.assertEqual(len(re.findall(r'<li><a href="[^"]*pokemon/\d+-', shell)), 966)
        self.assertIn(f'<link rel="canonical" href="{legal.SITE_URL}/">', shell)
        sitemap = (SITE / "sitemap.xml").read_text(encoding="utf8")
        pages = len(agents.PAGES) + 966 + len(landing.pages()) + len(toolpages.FOLDERS)
        self.assertEqual(sitemap.count("<url>"), pages * 2)
        self.assertIn("/en/pokemon/150-mewtwo/", sitemap)

    def test_no_cards_or_items_are_recommended(self) -> None:
        for rel in ("pokemon/150-mewtwo/index.html", "en/pokemon/150-mewtwo/index.html"):
            text = _visible((SITE / rel).read_text(encoding="utf8"))
            self.assertNotRegex(text, r"(?i)cartas por prioridad|cards by priority|objeto recomendado|recommended item")


class WhyRows(unittest.TestCase):
    """Qué factores nombra la ficha: los que más suman y restan, según la mitad del ranking."""

    def _entry(self, rank: int, effects: list[float]) -> dict:
        return {"r": {"rank": rank}, "why": [{"f": f"f{i}", "effect": e} for i, e in enumerate(effects)]}

    def test_top_half_names_two_ups_and_one_down(self) -> None:
        rows = static_ficha.why_rows(self._entry(10, [0.2, 0.1, 0.05, -0.03, -0.08]))
        self.assertEqual([w["effect"] for w in rows], [0.2, 0.1, -0.08])

    def test_bottom_half_names_one_up_and_two_downs(self) -> None:
        rows = static_ficha.why_rows(self._entry(900, [0.2, 0.1, -0.03, -0.08]))
        self.assertEqual([w["effect"] for w in rows], [0.2, -0.08, -0.03])

    def test_small_effects_are_left_out_and_others_fill_the_gap(self) -> None:
        rows = static_ficha.why_rows(self._entry(10, [0.2, 0.01, -0.005, 0.03]))
        self.assertEqual([w["effect"] for w in rows], [0.2, 0.03])
        self.assertEqual(static_ficha.why_rows(self._entry(900, [0.3, 0.2, 0.1])), [
            {"f": "f0", "effect": 0.3}, {"f": "f1", "effect": 0.2}, {"f": "f2", "effect": 0.1}])


def _faq_pairs(page: str) -> list[tuple[str, str]]:
    section = re.search(r'<section class="sheet faq".*?</section>', page, re.S)
    if not section:
        return []
    return [(html_lib.unescape(q), html_lib.unescape(a))
            for q, a in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", section.group(0), re.S)]


class FaqCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()

    def test_visible_faq_matches_jsonld_exactly(self) -> None:
        for rel in ("pokemon/150-mewtwo/index.html", "en/pokemon/150-mewtwo/index.html",
                    "pokemon/1000-gholdengo/index.html", "pokemon/829-gossifleur/index.html"):
            page = (SITE / rel).read_text(encoding="utf8")
            ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
            pairs = _faq_pairs(page)
            self.assertEqual(len(pairs), 3, rel)
            self.assertEqual(pairs, [(e["name"], e["acceptedAnswer"]["text"]) for e in ld["mainEntity"]], rel)

    def test_mewtwo_questions_are_the_player_ones(self) -> None:
        es = [q for q, _ in _faq_pairs((SITE / "pokemon" / "150-mewtwo" / "index.html").read_text(encoding="utf8"))]
        en = [q for q, _ in _faq_pairs((SITE / "en" / "pokemon" / "150-mewtwo" / "index.html").read_text(encoding="utf8"))]
        self.assertEqual(es, ["¿Vale la pena?", "¿Qué ataques le pongo?", "¿Cómo se consigue?"])
        self.assertEqual(en, ["Is it worth it?", "Which moves should I use?", "How do you get it?"])

    def test_faq_answers_do_not_repeat_the_name(self) -> None:
        for rel in ("pokemon/150-mewtwo/index.html", "en/pokemon/150-mewtwo/index.html"):
            page = (SITE / rel).read_text(encoding="utf8")
            section = re.search(r'<section class="sheet faq".*?</section>', page, re.S).group(0)
            self.assertNotIn("Mewtwo", section)

    def test_join_uses_e_before_i_sound(self) -> None:
        self.assertEqual(static_ficha._join(ES, ["Vozarrón", "Hipnosis"]), "Vozarrón e Hipnosis")
        self.assertEqual(static_ficha._join(ES, ["Psíquico", "Vozarrón", "Ímpetu"]), "Psíquico, Vozarrón e Ímpetu")
        self.assertEqual(static_ficha._join(ES, ["Vozarrón", "Hierba"]), "Vozarrón y Hierba")
        self.assertEqual(static_ficha._join(ES, ["Vozarrón", "Hielo"]), "Vozarrón y Hielo")
        self.assertEqual(static_ficha._join(ES, ["Vozarrón", "Hidropulso"]), "Vozarrón e Hidropulso")
        self.assertEqual(static_ficha._join(EN, ["Hyper Voice", "Impact"]), "Hyper Voice and Impact")
        self.assertEqual(static_ficha._join(ES, ["Solo"]), "Solo")
        self.assertEqual(static_ficha._join(ES, []), "")

    def test_faq_branches(self) -> None:
        plain = static_ficha._faqs(ES, "A", 87, "Cuerpo a cuerpo: Psíquico y Vozarrón.", "Kanto", False, "0,25", 400)
        self.assertEqual([a for _, a in plain], [
            "Sí, está entre los buenos: tier A, puesto 87 de 966.", "Cuerpo a cuerpo: Psíquico y Vozarrón.",
            "Sale en el banner Kanto. Cada tirada tiene un 0,25\u00a0% de probabilidad, así que de media hacen falta "
            "unas 400 tiradas, sin contar las garantías."])
        leg = static_ficha._faqs(ES, "B", 300, "A distancia: Vozarrón.", "Galar", True, "2", 51)
        self.assertTrue(leg[-1][1].startswith("Es de los legendarios y sale en el banner Galar."))
        en = static_ficha._faqs(EN, "D", 966, "Ranged: Hyper Voice, with Swords Dance.", "Galar", False, "2.0", 51)
        self.assertEqual(en[-1][1], "It is on the Galar banner. Each pull has a 2.0% chance, so on average it takes "
                                    "about 51 pulls, not counting pity guarantees.")


if __name__ == "__main__":
    unittest.main()
