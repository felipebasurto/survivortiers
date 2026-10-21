"""Builds cuerpo a cuerpo y a distancia (build/builds.py) y su texto en la ficha.

    python3 -m unittest build/test_builds.py
"""
from __future__ import annotations

import csv
import html as html_lib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import builds  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402


def _sample_dex(n: int = 1) -> list[int]:
    """Especies que tienen build cuerpo a cuerpo y a distancia."""
    return [d for d, groups in builds.space().items() if {"melee", "ranged"} <= set(groups.values())][:n]


def _kinds_by_dex() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    with (ROOT / "data" / "builds.csv").open(encoding="utf8", newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["dex"], set()).add(row["build"])
    return out


class Candidates(unittest.TestCase):
    def test_every_candidate_meets_the_rules(self) -> None:
        for dex in sorted(builds.space())[:60]:
            for group, build in builds.candidates(dex).items():
                with self.subTest(dex=dex, group=group):
                    self.assertEqual(builds.violations(dex, build, group), [])

    def test_attack_buff_raises_an_attack_of_the_group(self) -> None:
        self.assertEqual(builds.attack_buffs(["ember", "flamethrower"]), ["nasty-plot"])
        self.assertEqual(builds.attack_buffs(["ember", "meteor-mash"], dragon_dance=False), ["nasty-plot", "swords-dance"])

    def test_every_shape_fills_the_four_slots(self) -> None:
        for group in builds.variants(["ember", "meteor-mash", "rock-throw"]) + builds.variants(["ember", "meteor-mash"]):
            self.assertEqual(len(group.split("+")), builds.picks.BOND_SLOTS, group)


class Violations(unittest.TestCase):
    def test_melee_build_without_melee_move_is_reported(self) -> None:
        dex = _sample_dex()[0]
        group = next(g for g, b in builds.candidates(dex).items() if b == "ranged")
        self.assertTrue(builds.violations(dex, "melee", group))

    def test_ranged_build_with_melee_move_is_reported(self) -> None:
        dex = _sample_dex()[0]
        group = next(g for g, b in builds.candidates(dex).items() if b == "melee")
        self.assertTrue(builds.violations(dex, "ranged", group))


class Moves(unittest.TestCase):
    def test_build_moves_puts_boosts_last(self) -> None:
        moves, n = builds.build_moves("hyper-beam+poison-sting+sludge+swords-dance")
        self.assertEqual(moves, ["hyper-beam", "poison-sting", "sludge", "swords-dance"])
        self.assertEqual(n, 1)
        moves, n = builds.build_moves("sludge+seed-bomb+nasty-plot+harden")
        self.assertEqual(moves, ["sludge", "seed-bomb", "nasty-plot", "harden"])
        self.assertEqual(n, 2)


class Text(unittest.TestCase):
    def _b(self, score: float) -> dict:
        return {"score": score}

    def test_winner_and_tie(self) -> None:
        self.assertEqual(static_ficha._winner({"melee": self._b(50), "ranged": self._b(40)}), "melee")
        self.assertEqual(static_ficha._winner({"melee": self._b(40), "ranged": self._b(50)}), "ranged")
        self.assertIsNone(static_ficha._winner({"melee": self._b(45), "ranged": self._b(45)}))
        self.assertEqual(static_ficha._winner({"melee": None, "ranged": self._b(45)}), "ranged")
        self.assertIsNone(static_ficha._winner({"melee": None, "ranged": None}))

    def test_small_gap_says_so_plainly(self) -> None:
        win, low = self._b(100.0), self._b(98.0)
        text = static_ficha._verdict(ES, "ranged", low, win, "melee")
        self.assertIn("Solo un 2\u00a0% peor que la build cuerpo a cuerpo.", text)
        text_en = static_ficha._verdict(EN, "ranged", low, win, "melee")
        self.assertIn("Only 2% below the melee build.", text_en)

    def test_large_gap_drops_the_adverb(self) -> None:
        win, low = self._b(100.0), self._b(70.0)
        self.assertIn("Un 30\u00a0% peor que la build cuerpo a cuerpo.", static_ficha._verdict(ES, "ranged", low, win, "melee"))

    def test_winner_is_marked_and_missing_other_is_silent(self) -> None:
        win = self._b(100.0)
        self.assertIn("is-best", static_ficha._verdict(ES, "melee", win, self._b(90.0), "melee"))
        self.assertEqual(static_ficha._verdict(ES, "melee", win, None, "melee"), "")

    def test_missing_build_renders_nothing(self) -> None:
        self.assertEqual(static_ficha._build_option(ES, {}, {}, "melee", None, None, None), "")
        self.assertEqual(static_ficha._build_option(EN, {}, {}, "ranged", None, None, None), "")


class FichaBuildLayout(unittest.TestCase):
    """Las fichas ya generadas (python3 build/render.py): una especie sin build cuerpo a cuerpo no pinta su caja."""

    def _page(self, prefix: str, slug: str) -> str:
        path = ROOT / "site" / prefix / "pokemon" / slug / "index.html"
        self.assertTrue(path.is_file(), "falta la ficha estática: python3 build/render.py")
        return path.read_text(encoding="utf8")

    def test_single_build_species_has_one_full_width_box(self) -> None:
        for prefix in ("", "en"):
            page = self._page(prefix, "94-gengar")
            with self.subTest(prefix=prefix):
                self.assertEqual(page.count('class="bd-opt'), 1)
                self.assertIn('data-build="ranged"', page)
                self.assertNotIn('data-build="melee"', page)
                self.assertIn('class="bd-pair is-single"', page)
                self.assertNotIn("bd-none", page)
                self.assertNotIn("is-none", page)
                self.assertNotIn("bd-note", page)

    def test_species_with_both_builds_is_unchanged(self) -> None:
        for prefix, lang in (("", ES), ("en", EN)):
            page = self._page(prefix, "354-banette")
            with self.subTest(prefix=prefix):
                self.assertEqual(page.count('class="bd-opt'), 2)
                self.assertIn('data-build="melee"', page)
                self.assertIn('data-build="ranged"', page)
                self.assertIn('class="bd-pair"', page)
                self.assertNotIn("is-single", page)

    def test_each_build_starts_with_its_own_first_attack(self) -> None:
        expect = {("", "94-gengar"): {"ranged": "Viento Aciago"},
                  ("en", "94-gengar"): {"ranged": "Ominous Wind"},
                  ("", "354-banette"): {"melee": "Lengüetazo", "ranged": "Giro Rápido"},
                  ("en", "354-banette"): {"melee": "Lick", "ranged": "Rapid Spin"}}
        for (prefix, slug), starts in expect.items():
            page = self._page(prefix, slug)
            for kind, name in starts.items():
                with self.subTest(prefix=prefix, slug=slug, kind=kind):
                    box = re.search(rf'<article class="bd-opt[^"]*" data-build="{kind}">.*?</article>', page, re.S).group(0)
                    self.assertEqual(box.count("is-start"), 1)
                    row = re.search(r'<li class="bd-row[^"]*is-start">.*?</li>', box, re.S).group(0)
                    self.assertIn(f'<span class="bd-nm">{name}</span>', row)
                    self.assertIn("bd-pill is-gold", row)
                    self.assertIn(">" + ("Start with" if prefix else "Empieza con") + "<", row)

    def test_default_start_is_a_small_note_without_a_row(self) -> None:
        notes = {"": "De serie: Bola Sombra; cámbialo con Movimiento inicial (400 monedas)",
                 "en": "Default: Shadow Ball; change it with Starting Move (400 coins)"}
        for prefix, note in notes.items():
            page = self._page(prefix, "94-gengar")
            with self.subTest(prefix=prefix):
                self.assertIn(f'<p class="bd-default">{note}</p>', page)
                self.assertEqual(page.count("bd-default"), 1)
                self.assertNotIn("bd-start", page)

    def test_special_attacker_text_never_mentions_melee(self) -> None:
        for prefix in ("", "en"):
            page = self._page(prefix, "94-gengar")
            text = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text) + " ".join(re.findall(r'content="([^"]*)"', page))
            with self.subTest(prefix=prefix):
                self.assertNotRegex(text, r"(?i)cuerpo a cuerpo|melee|dos builds|two builds")

    def test_shape_follows_the_build_data(self) -> None:
        for dex, kinds in list(_kinds_by_dex().items())[:40]:
            slug = next(p.name for p in (ROOT / "site" / "pokemon").glob(f"{dex}-*"))
            page = self._page("", slug)
            with self.subTest(dex=dex):
                self.assertEqual(page.count('class="bd-opt'), len(kinds))
                self.assertEqual("melee" in kinds, 'data-build="melee"' in page)


if __name__ == "__main__":
    unittest.main()
