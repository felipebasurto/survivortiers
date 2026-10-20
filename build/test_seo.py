"""Lo que un rastreador sin JavaScript lee: portada, método, robots, llms.txt, sitemap y plantilla de ficha.

    python3 -m unittest build/test_seo.py

Necesita site/ generado: python3 build/catalog.py && python3 build/render.py
"""
from __future__ import annotations

import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import agents  # noqa: E402
import legal  # noqa: E402
from i18n import EN, ES  # noqa: E402

SITE = ROOT / "site"
LD_RE = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


def _read(rel: str) -> str:
    return (SITE / rel).read_text(encoding="utf8")


def _index() -> list[dict]:
    return json.loads(_read("data/pokemon-index.json"))


def _graph(html: str) -> list[dict]:
    nodes = []
    for raw in LD_RE.findall(html):
        doc = json.loads(raw.replace("<\\/", "</"))
        nodes += doc.get("@graph", [doc])
    return nodes


class Home(unittest.TestCase):
    def test_tier_list_comes_first_and_shows_the_top_five(self) -> None:
        index = _index()
        for rel, lang in (("index.html", ES), ("en/index.html", EN)):
            html = _read(rel)
            self.assertNotIn('<p class="tagline">', html)
            tiers = html[html.index('id="tierlist"'):]
            for p in sorted(index, key=lambda p: p["r"][0])[:5]:
                self.assertIn(lang.mon(p), html_lib.unescape(tiers))

    def test_svg_defs_come_after_the_h1(self) -> None:
        for rel in ("index.html", "pokemon/150-mewtwo/index.html"):
            html = _read(rel)
            self.assertLess(html.index("<h1>"), html.index('class="sprites-defs"'), rel)

    def test_json_ld_has_website_collection_and_dataset_with_date(self) -> None:
        for rel in ("index.html", "en/index.html"):
            nodes = _graph(_read(rel))
            kinds = {n["@type"] for n in nodes}
            self.assertTrue({"WebSite", "CollectionPage", "Dataset"} <= kinds, rel)
            page = next(n for n in nodes if n["@type"] == "CollectionPage")
            self.assertRegex(page["dateModified"], r"^\d{4}-\d{2}-\d{2}$")

    def test_hreflang_pair_is_absolute_on_the_home(self) -> None:
        es, en = _read("index.html"), _read("en/index.html")
        for html in (es, en):
            self.assertIn(f'hreflang="es" href="{legal.SITE_URL}/"', html)
            self.assertIn(f'hreflang="en" href="{legal.SITE_URL}/en/"', html)
            self.assertIn(f'hreflang="x-default" href="{legal.SITE_URL}/"', html)
        self.assertIn(f'rel="canonical" href="{legal.SITE_URL}/en/"', en)


class Method(unittest.TestCase):
    def test_method_describes_the_current_pipeline(self) -> None:
        es, en = _read("metodo.html"), _read("en/metodo.html")
        for html in (es, en):
            self.assertIn(legal.UPDATED_COMMIT, html)
            self.assertNotIn("ficha pesa", html)
            self.assertNotIn("sheet weighs", html)
            self.assertNotIn("2.000 ordenaciones", html)
        self.assertIn("daño total que hace", es)
        self.assertIn("total damage it deals", en)
        self.assertIn("Sin daño vale 0", es)
        self.assertIn("With no damage it is worth 0", en)

    def test_method_numbers_come_from_the_code(self) -> None:
        from catalog import METHOD
        self.assertEqual(METHOD["score"], {"capSeconds": 1800})
        stats_rs = (ROOT / "simulator" / "sim-rs" / "src" / "stats.rs").read_text(encoding="utf8")
        self.assertNotIn("DPS_REF", stats_rs)
        self.assertNotIn("KPM_REF", stats_rs)
        make = (ROOT / "build" / "make_definitive.py").read_text(encoding="utf8")
        self.assertIn(f"REPEATS = {METHOD['repeats']}", make)


class AgentFiles(unittest.TestCase):
    def test_robots_allows_the_named_bots_and_points_to_the_sitemap(self) -> None:
        robots = _read("robots.txt")
        for bot in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Google-Extended", "Bingbot"):
            self.assertIn(f"User-agent: {bot}\nAllow: /\n", robots)
        self.assertNotIn("Disallow", robots)
        self.assertIn(f"Sitemap: {legal.SITE_URL}/sitemap.xml", robots)
        self.assertEqual(set(agents.ALLOWED_BOTS), set(re.findall(r"User-agent: (?!\*)(\S+)", robots)))

    def test_llms_txt_states_what_the_site_is_the_method_and_the_patch(self) -> None:
        text = _read("llms.txt")
        self.assertTrue(text.startswith("# SurvivorTiers"))
        self.assertIn(legal.freshness_text(EN), text)
        self.assertIn("Best five right now", text)
        self.assertIn("time alive, damage dealt and kills", text)
        self.assertIn(f"{legal.SITE_URL}/en/metodo", text)
        self.assertNotIn("sheet percentiles", text)
        full = _read("llms-full.txt")
        self.assertIn("No constants.", full)
        self.assertNotIn("Three pieces", full)

    def test_sitemap_has_lastmod_and_hreflang_for_every_url(self) -> None:
        sitemap = _read("sitemap.xml")
        entries = re.findall(r"<url>.*?</url>", sitemap, re.S)
        self.assertGreater(len(entries), 1900)
        for entry in entries:
            self.assertRegex(entry, r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>")
            self.assertEqual(entry.count("<xhtml:link"), 3)
        for loc in ("/metodo", "/en/metodo", "/ataques", "/en/ataques", "/pokemon/150-mewtwo/", "/en/pokemon/150-mewtwo/"):
            self.assertIn(f"<loc>{legal.SITE_URL}{loc}</loc>", sitemap)

    def test_indexnow_key_is_served_from_the_root(self) -> None:
        import indexnow
        key = indexnow.key_file()
        self.assertEqual(_read(key.name).strip(), key.stem)


if __name__ == "__main__":
    unittest.main()
