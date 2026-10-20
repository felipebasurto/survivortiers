"""Fichas estáticas: slug, probabilidad de tirada y una página de Mewtwo ya generada.

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

import sitefixture  # noqa: E402
import legal  # noqa: E402
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

    def test_ficha_has_no_repertorio_note(self) -> None:
        for page in (SITE / "pokemon" / "150-mewtwo" / "index.html", SITE / "en" / "pokemon" / "150-mewtwo" / "index.html"):
            html = page.read_text(encoding="utf8")
            self.assertNotIn("rep-note", html, page)
            self.assertNotIn("rep-warn", html, page)
        for source in ("ficha.js", "style.css"):
            self.assertNotIn("rep-warn", (ROOT / "src" / source).read_text(encoding="utf8"), source)

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
        moves.update({m["id"]: m for m in json.loads((SITE / "data" / "moves_unranked.json").read_text(encoding="utf8"))})
        ids, n_boost = species["d"]["150"][9][2], species["d"]["150"][9][5]
        game = legal.GAME_NAME
        self.assertIn(f"<title>Mewtwo en {game}: tier {row['tier']}, mejor build y ataques | SurvivorTiers</title>", es)
        self.assertIn(f"<title>Mewtwo in {game}: {row['tier']} tier, best build and moves | SurvivorTiers</title>", en)
        for html, rank_word in ((es, "puesto"), (en, "rank")):
            self.assertRegex(html, r"<h1>Mewtwo <span")
            self.assertRegex(html, r'<img class="px"[^>]* alt="[^"]*Mewtwo[^"]*"')
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
            self.assertIn(legal.UPDATED_COMMIT, text)
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
        self.assertNotIn("necesita JavaScript", _visible(shell))
        self.assertEqual(len(re.findall(r'<li><a href="[^"]*pokemon/\d+-', shell)), 966)
        self.assertIn(f'<link rel="canonical" href="{legal.SITE_URL}/">', shell)
        sitemap = (SITE / "sitemap.xml").read_text(encoding="utf8")
        self.assertEqual(sitemap.count("<url>"), (8 + 966 + 22 + len(toolpages.FOLDERS) + 1) * 2)
        self.assertIn("/pokemon/150-mewtwo/", sitemap)
        self.assertIn("/en/pokemon/150-mewtwo/", sitemap)
        robots = (SITE / "robots.txt").read_text(encoding="utf8")
        self.assertIn(f"Sitemap: {legal.SITE_URL}/sitemap.xml", robots)


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
            self.assertEqual(len(pairs), 4, rel)
            self.assertEqual(pairs, [(e["name"], e["acceptedAnswer"]["text"]) for e in ld["mainEntity"]], rel)

    def test_mewtwo_questions_are_the_player_ones(self) -> None:
        es = [q for q, _ in _faq_pairs((SITE / "pokemon" / "150-mewtwo" / "index.html").read_text(encoding="utf8"))]
        en = [q for q, _ in _faq_pairs((SITE / "en" / "pokemon" / "150-mewtwo" / "index.html").read_text(encoding="utf8"))]
        self.assertEqual(es, ["¿Vale la pena?", "¿Qué ataques le pongo?", "¿Qué cartas le conviene coger?", "¿Cómo se consigue?"])
        self.assertEqual(en, ["Is it worth it?", "Which moves should I use?", "Which upgrade cards should I take?",
                              "How do you get it?"])

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
        cards = "Según nuestra simulación, en este orden: Imán una vez y después Vigor."
        plain = static_ficha._faqs(ES, "A", 87, "Cuerpo a cuerpo: Psíquico y Vozarrón.", cards, "Kanto", False, "0,25", 400)
        self.assertEqual(plain[1][1], "Cuerpo a cuerpo: Psíquico y Vozarrón.")
        self.assertEqual(plain[0][1], "Sí, está entre los buenos: tier A, puesto 87 de 966.")
        self.assertEqual(plain[-1][1], "Sale en el banner Kanto. Cada tirada tiene un 0,25\u00a0% de probabilidad, "
                                       "así que de media hacen falta unas 400 tiradas, sin contar las garantías.")
        one = static_ficha._faqs(ES, "B", 300, "A distancia: Vozarrón y Golpe Cuerpo, con Danza Espada.", "", "Galar",
                                 True, "2", 51)
        self.assertEqual([q for q, _ in one], ["¿Vale la pena?", "¿Qué ataques le pongo?", "¿Cómo se consigue?"])
        self.assertTrue(one[-1][1].startswith("Es de los legendarios y sale en el banner Galar."))
        en = static_ficha._faqs(EN, "D", 966, "Ranged: Hyper Voice, with Swords Dance.", "Based on our simulation, "
                                "in this order: Reflexes.", "Galar", False, "2.0", 51)
        self.assertEqual(en[1][1], "Ranged: Hyper Voice, with Swords Dance.")
        self.assertEqual(en[-1][1], "It is on the Galar banner. Each pull has a 2.0% chance, so on average it takes "
                                    "about 51 pulls, not counting pity guarantees.")


if __name__ == "__main__":
    unittest.main()
