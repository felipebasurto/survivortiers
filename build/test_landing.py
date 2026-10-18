"""Páginas de consulta, JSON-LD de las páginas, enlaces, línea de datos, sitemap, IndexNow y similitud de fichas.

    python3 -m unittest build/test_landing.py

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

import dupcheck  # noqa: E402
import landing  # noqa: E402
import legal  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402
from slugs import species_path  # noqa: E402

SITE = ROOT / "site"
LD_RE = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
NAME_RE = re.compile(r'<span class="nm">(.*?)</span>')
PASSIVE_RE = re.compile(r'<span class="ql-name">(.*?)</span>')


def _read(rel: str) -> str:
    return (SITE / rel).read_text(encoding="utf8")


def _page_rel(lang, page) -> str:
    return ("en/" if lang.en else "") + landing.rel(lang, page)


def _meta() -> dict:
    return json.loads(_read("data/meta.json"))


def _ld(text: str) -> dict:
    m = LD_RE.search(text)
    return json.loads(m.group(1).replace("<\\/", "</"))


class LandingPages(unittest.TestCase):
    def test_every_page_exists_in_both_languages(self) -> None:
        for page in landing.pages():
            for lang in (ES, EN):
                self.assertTrue((SITE / _page_rel(lang, page)).is_file(), _page_rel(lang, page))

    def test_repertorio_note_only_on_starters_page(self) -> None:
        for page in landing.pages():
            for lang in (ES, EN):
                html = _read(_page_rel(lang, page))
                if page.key == "starters":
                    self.assertEqual(html.count('class="rep-note"'), 1, _page_rel(lang, page))
                else:
                    self.assertNotIn("rep-note", html, _page_rel(lang, page))

    def test_itemlist_matches_visible_list_in_order(self) -> None:
        for page in landing.pages():
            for lang in (ES, EN):
                text = _read(_page_rel(lang, page))
                items = _ld(text)["mainEntity"]["itemListElement"]
                self.assertEqual(_ld(text)["mainEntity"]["numberOfItems"], len(items))
                found = PASSIVE_RE.findall(text) if page.key == "passives" else NAME_RE.findall(text)
                self.assertEqual([html_lib.unescape(n) for n in found], [i["name"] for i in items], _page_rel(lang, page))

    def test_answer_comes_before_the_list(self) -> None:
        for page in landing.pages():
            for lang in (ES, EN):
                text = _read(_page_rel(lang, page))
                h1, lede = text.index("<h1>"), text.index('<p class="ql-lede">')
                first_list = text.index('<section class="ql-list"')
                self.assertLess(h1, lede)
                self.assertLess(lede, first_list)

    def test_lede_names_the_first_rows(self) -> None:
        for page in landing.pages():
            if page.key == "passives":
                continue
            for lang in (ES, EN):
                text = _read(_page_rel(lang, page))
                lede = html_lib.unescape(re.search(r'<p class="ql-lede">(.*?)</p>', text, re.S).group(1))
                names = [i["name"] for i in _ld(text)["mainEntity"]["itemListElement"]]
                self.assertIn(names[0], lede, _page_rel(lang, page))

    def test_canonical_and_hreflang_pairs(self) -> None:
        for page in landing.pages():
            for lang in (ES, EN):
                text = _read(_page_rel(lang, page))
                self.assertIn(f'rel="canonical" href="{landing.url(lang, page)}"', text)
                self.assertIn(f'hreflang="es" href="{landing.url(ES, page)}"', text)
                self.assertIn(f'hreflang="en" href="{landing.url(EN, page)}"', text)
                self.assertIn(f'hreflang="x-default" href="{landing.url(ES, page)}"', text)

    def test_type_pages_list_only_their_type(self) -> None:
        index = json.loads(_read("data/pokemon-index.json"))
        for t in landing.TYPE_KEYS:
            page = landing.page_for(f"type:{t}")
            members = {p["dex"] for p in index if t in p["types"]}
            listed = {i for i in re.findall(r'data-dex="(\d+)"', _read(_page_rel(ES, page)))}
            self.assertTrue({int(d) for d in listed} <= members, t)

    def test_page_links_back_to_the_tier_list(self) -> None:
        for page in landing.pages():
            up = "../" * page.es.count("/")
            self.assertIn(f'href="{up}index.html"', _read(_page_rel(ES, page)), page.key)


class LinksAndFreshness(unittest.TestCase):
    def test_home_links_every_landing_page(self) -> None:
        home = _read("index.html")
        for page in landing.pages():
            self.assertIn(f'href="{landing.folder(ES, page)}"', home, page.key)

    def test_every_ficha_links_the_tier_list_and_its_lists(self) -> None:
        index = json.loads(_read("data/pokemon-index.json"))
        for p in index[:: max(1, len(index) // 40)]:
            path = f"pokemon/{species_path(p['dex'], p['nameEn'])}/index.html"
            text = _read(path)
            self.assertIn('href="../../index.html"', text, path)
            self.assertIn('href="../../mejores-pokemon/"', text, path)
            for t in p["types"]:
                self.assertIn(f'href="../../{landing.folder(ES, landing.page_for(f"type:{t}"))}"', text, path)

    def test_freshness_line_on_index_ficha_and_landing(self) -> None:
        meta = _meta()
        date, sha = meta["generatedAt"][:10], meta["gameCommit"][:7]
        es_line = f"Datos del juego: commit {sha} · actualizado {date}"
        en_line = f"Game data: commit {sha} · updated {date}"
        self.assertIn(es_line, _read("index.html"))
        self.assertIn(en_line, _read("en/index.html"))
        self.assertIn(es_line, _read("pokemon/150-mewtwo/index.html"))
        self.assertIn(en_line, _read("en/pokemon/150-mewtwo/index.html"))
        self.assertIn(es_line, _read("mejores-pokemon/index.html"))
        self.assertIn(en_line, _read("en/best-pokemon/index.html"))

    def test_date_modified_in_structured_data(self) -> None:
        meta = _meta()
        date = meta["generatedAt"][:10]
        self.assertEqual(_ld(_read("pokemon/150-mewtwo/index.html"))["dateModified"], date)
        self.assertEqual(_ld(_read("mejores-tipo/psiquico/index.html"))["dateModified"], date)

    def test_sitemap_has_landing_pages_in_both_languages(self) -> None:
        sitemap = _read("sitemap.xml")
        for page in landing.pages():
            self.assertIn(f"<loc>{legal.SITE_URL}/{page.es}</loc>", sitemap, page.key)
            self.assertIn(f"<loc>{legal.SITE_URL}/en/{page.en}</loc>", sitemap, page.key)


class Summaries(unittest.TestCase):
    def test_marks_are_stripped_and_text_kept(self) -> None:
        raw = "Rápido, [hp-|poca vida] y [m.start:vine-whip|Látigo Cepa]. Lo sube [up:best_move|Residuos]."
        self.assertEqual(static_ficha.summary_plain(raw), "Rápido, poca vida y Látigo Cepa. Lo sube Residuos.")

    def test_ficha_shows_the_plain_summary(self) -> None:
        summaries = json.loads((ROOT / "build" / "out" / "public" / "summaries-es.json").read_text(encoding="utf8"))
        plain = static_ficha.summary_plain(summaries["150"])
        text = _read("pokemon/150-mewtwo/index.html")
        self.assertIn(html_lib.escape(plain), text)
        self.assertNotIn("[m.", text)


class Similarity(unittest.TestCase):
    def test_identical_pages_score_one(self) -> None:
        words = "a b c d e f g h".split()
        s = dupcheck.shingles(words)
        self.assertEqual(dupcheck.jaccard(s, s), 1.0)

    def test_disjoint_pages_score_zero(self) -> None:
        a = dupcheck.shingles("a b c d e f g h".split())
        b = dupcheck.shingles("p q r s t u v w".split())
        self.assertEqual(dupcheck.jaccard(a, b), 0.0)

    def test_visible_words_skip_scripts_and_markup(self) -> None:
        page = "<main><h1>Mewtwo</h1><script>var x=1;</script><p>tier <b>A</b></p></main>"
        self.assertEqual(dupcheck.visible_words(page), ["mewtwo", "tier", "a"])


if __name__ == "__main__":
    unittest.main()
