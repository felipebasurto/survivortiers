"""Builds de la ficha (build/builds.py): salen de los grupos ya simulados, sin reglas a mano ni simulación nueva.

    python3 -m unittest build/test_builds.py
"""
from __future__ import annotations

import csv
import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import builds  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402

SINISTCHA, GENGAR, BANETTE, CORVISQUIRE = 1013, 94, 354, 822


def _published() -> list[dict]:
    with (ROOT / "data" / "builds.csv").open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def _kinds_by_dex() -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for row in _published():
        out.setdefault(int(row["dex"]), set()).add(row["build"])
    return out


def _move_names(prefix: str) -> dict[str, str]:
    moves = json.loads((ROOT / "site" / "data" / "moves.json").read_text(encoding="utf8"))
    return {m["id"]: (m["en"]["name"] if prefix else m["name"]) for m in moves}


class Rules(unittest.TestCase):
    def test_published_rows_meet_the_rules(self) -> None:
        for row in _published():
            with self.subTest(dex=row["dex"], build=row["build"]):
                self.assertEqual(builds.violations(int(row["dex"]), row["build"], row["group"]), [])

    def test_offensive_builds_are_three_attacks_and_their_buff(self) -> None:
        for row in _published():
            if row["build"] == builds.DEFENSIVE:
                continue
            attacks, buff, fourth = builds.picks.split_group(row["group"])
            cat = builds.offensive_category(attacks)
            with self.subTest(dex=row["dex"], group=row["group"]):
                self.assertEqual(len(set(attacks)), 3)
                self.assertIsNone(fourth)
                self.assertEqual(buff, builds.ATTACK_BUFF[cat])

    def test_no_filler_in_any_published_build(self) -> None:
        for row in _published():
            attacks, _, _ = builds.picks.split_group(row["group"])
            for mid in attacks:
                with self.subTest(dex=row["dex"], move=mid):
                    self.assertFalse(builds.is_filler(int(row["dex"]), mid))

    def test_defensive_builds_carry_fortaleza_and_only_those(self) -> None:
        rows = [r for r in _published() if r["build"] == builds.DEFENSIVE]
        self.assertGreater(len(rows), 700)
        for row in rows:
            self.assertEqual(row["group"].split("+")[-1], "harden", row["group"])
        for row in _published():
            if row["build"] != builds.DEFENSIVE:
                self.assertNotIn("harden", row["group"].split("+"))

    def test_special_only_groups_never_have_a_melee_build(self) -> None:
        for row in _published():
            if row["build"] == "melee":
                attacks, _, _ = builds.picks.split_group(row["group"])
                self.assertEqual(builds.offensive_category(attacks), "physical", row["group"])

    def test_published_rows_are_what_the_code_picks_from_the_sim_files(self) -> None:
        got = {(int(r["dex"]), r["build"]): (r["group"], r["source"]) for r in builds.assemble()}
        have = {(int(r["dex"]), r["build"]): (r["group"], r["source"]) for r in _published()}
        self.assertEqual(got, have)

    def test_every_species_starts_with_a_damaging_attack(self) -> None:
        starts = builds.starts()
        self.assertEqual(len(starts), 966)
        for dex, mid in starts.items():
            self.assertNotEqual(mid, builds.NOT_AN_ATTACK, dex)
            self.assertNotEqual(builds.category(mid), "status", dex)

    def test_sinistcha_does_not_start_with_its_default_attack(self) -> None:
        self.assertEqual(builds.starts()[SINISTCHA], "shadow-ball")
        self.assertEqual(builds.default_starts()[SINISTCHA], "vine-whip")


class Filler(unittest.TestCase):
    def test_hyper_beam_stays_because_the_tier_list_keeps_it(self) -> None:
        self.assertFalse(builds.is_filler(GENGAR, "hyper-beam"))

    def test_weak_normal_attacks_are_filler_for_other_types(self) -> None:
        for mid in ("hyper-voice", "tackle", "body-slam", "rapid-spin", "quick-attack", "substitute"):
            with self.subTest(move=mid):
                self.assertTrue(builds.is_filler(SINISTCHA, mid))

    def test_a_normal_type_species_keeps_its_own_type(self) -> None:
        self.assertFalse(builds.is_filler(143, "hyper-voice"))
        self.assertTrue(builds.is_filler(143, "substitute"))


class Violations(unittest.TestCase):
    def test_filler_is_reported(self) -> None:
        group = "ominous-wind+hyper-voice+seed-bomb+nasty-plot"
        self.assertTrue(builds.violations(SINISTCHA, "ranged", group))

    def test_harden_is_not_an_offensive_build(self) -> None:
        group = next(r["group"] for r in _published() if r["build"] == builds.DEFENSIVE)
        dex = int(next(r["dex"] for r in _published() if r["build"] == builds.DEFENSIVE))
        self.assertTrue(builds.violations(dex, "ranged", group))
        self.assertEqual(builds.violations(dex, builds.DEFENSIVE, group), [])

    def test_a_melee_build_is_not_a_ranged_one(self) -> None:
        row = next(r for r in _published() if r["build"] == "melee")
        self.assertTrue(builds.violations(int(row["dex"]), "ranged", row["group"]))
        row = next(r for r in _published() if r["build"] == "ranged")
        self.assertTrue(builds.violations(int(row["dex"]), "melee", row["group"]))


class Choose(unittest.TestCase):
    @staticmethod
    def _row(group: str, score: float, lo: float, seconds: float, boot_lo: float) -> dict:
        return {"group": group, "median_score": str(score), "mean_score": str(score), "median_kills": "100",
                "median_dealt": "1000", "median_s": str(seconds), "score_lo": str(lo), "boot_lo": str(boot_lo)}

    def test_start_lead_wins_inside_the_noise(self) -> None:
        best = self._row("hex+shadow-ball+hyper-beam+nasty-plot", 100, 90, 100, 90)
        near = self._row("shadow-ball+hex+hyper-beam+nasty-plot", 95, 85, 95, 85)
        self.assertEqual(builds.choose([best, near], "shadow-ball")["group"], near["group"])

    def test_start_lead_loses_outside_the_noise(self) -> None:
        best = self._row("hex+shadow-ball+hyper-beam+nasty-plot", 100, 90, 100, 90)
        far = self._row("shadow-ball+hex+hyper-beam+nasty-plot", 80, 70, 80, 70)
        self.assertEqual(builds.choose([best, far], "shadow-ball")["group"], best["group"])

    def test_both_time_and_score_must_stay_inside(self) -> None:
        best = self._row("hex+shadow-ball+hyper-beam+nasty-plot", 100, 90, 100, 90)
        slow = self._row("shadow-ball+hex+hyper-beam+nasty-plot", 95, 85, 80, 70)
        self.assertEqual(builds.choose([best, slow], "shadow-ball")["group"], best["group"])


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

    def test_defense_verdict_reports_time_and_damage(self) -> None:
        off = {"time": 160.0, "dealt": 20000}
        deff = {"time": 170.0, "dealt": 15000}
        self.assertEqual(static_ficha.defense_verdict(ES, deff, off),
                         "Con Fortaleza, frente a la ofensiva: aguantas 10,0 s más y haces un 25\u00a0% menos de daño.")
        self.assertEqual(static_ficha.defense_verdict(EN, deff, off),
                         "With Harden, against the offensive build: you last 10.0 s longer and you deal 25% less damage.")
        self.assertEqual(static_ficha.defense_verdict(ES, deff, None), "")


class FichaBuildLayout(unittest.TestCase):
    """Las fichas ya generadas (python3 build/render.py)."""

    def _page(self, prefix: str, slug: str) -> str:
        path = ROOT / "site" / prefix / "pokemon" / slug / "index.html"
        self.assertTrue(path.is_file(), "falta la ficha estática: python3 build/render.py")
        return path.read_text(encoding="utf8")

    def _slug(self, dex: int) -> str:
        return next(p.name for p in (ROOT / "site" / "pokemon").glob(f"{dex}-*"))

    def _build_section(self, prefix: str, dex: int) -> str:
        page = self._page(prefix, self._slug(dex))
        return re.search(r'id="build".*?<p class="bd-brand">', page, re.S).group(0)

    def _text(self, html: str) -> str:
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
        return html_lib.unescape(re.sub(r"<[^>]+>", " ", text))

    def test_the_start_is_one_gold_row_outside_the_builds(self) -> None:
        for prefix in ("", "en"):
            names = _move_names(prefix)
            for dex in (SINISTCHA, GENGAR, BANETTE, CORVISQUIRE):
                with self.subTest(prefix=prefix, dex=dex):
                    page = self._page(prefix, self._slug(dex))
                    block = re.search(r'<div class="bd-block bd-start">.*?</div>', page, re.S).group(0)
                    self.assertEqual(page.count("is-start"), 1)
                    self.assertEqual(block.count("is-start"), 1)
                    self.assertIn("bd-pill is-gold", block)
                    self.assertIn(f'<span class="bd-nm">{names[builds.starts()[dex]]}</span>', block)
                    self.assertEqual(page.count('class="bd-default"'), 1)

    def test_default_start_is_a_small_note_next_to_the_start(self) -> None:
        notes = {"": "De serie: Látigo Cepa; cámbialo con Movimiento inicial (400 monedas)",
                 "en": "Default: Vine Whip; change it with Starting Move (400 coins)"}
        for prefix, note in notes.items():
            page = self._page(prefix, self._slug(SINISTCHA))
            self.assertIn(f'<p class="bd-default">{note}</p>', page)
            self.assertIn('<span class="bd-nm">' + ("Shadow Ball" if prefix else "Bola Sombra") + "</span>", page)

    def test_default_start_that_is_the_best_one_says_so(self) -> None:
        dex = next(d for d, mid in builds.starts().items() if builds.default_starts()[d] == mid)
        for prefix, lang in (("", ES), ("en", EN)):
            self.assertIn(f'<p class="bd-default">{html_lib.escape(lang.t("build_default_same"))}</p>',
                          self._page(prefix, self._slug(dex)))

    def test_no_offensive_row_is_marked_as_the_start(self) -> None:
        for dex in (SINISTCHA, GENGAR, BANETTE):
            section = self._build_section("", dex)
            for box in re.findall(r'<article class="bd-opt.*?</article>', section, re.S):
                self.assertNotIn("is-start", box)
                self.assertNotIn("bd-pill is-gold", box)

    def test_shape_follows_the_build_data(self) -> None:
        for dex, kinds in sorted(_kinds_by_dex().items())[:40] + [(SINISTCHA, _kinds_by_dex()[SINISTCHA])]:
            page = self._page("", self._slug(dex))
            offensive = kinds - {builds.DEFENSIVE}
            with self.subTest(dex=dex):
                self.assertEqual(page.count('class="bd-opt'), len(offensive))
                self.assertEqual("melee" in kinds, 'data-build="melee"' in page)
                self.assertEqual(builds.DEFENSIVE in kinds, 'data-build="defensive"' in page)

    def test_single_offensive_build_has_one_full_width_box(self) -> None:
        for prefix, lang in (("", ES), ("en", EN)):
            page = self._page(prefix, self._slug(SINISTCHA))
            with self.subTest(prefix=prefix):
                self.assertEqual(page.count('class="bd-opt'), 1)
                self.assertIn('class="bd-pair is-single"', page)
                self.assertNotIn('data-build="melee"', page)
                self.assertNotIn("bd-note", page)
                self.assertNotIn('<p class="bd-cap">' + html_lib.escape(lang.t("bd_pair_cap")), page)

    def test_defensive_variant_shows_its_time_next_to_the_offensive_one(self) -> None:
        for prefix, lang in (("", ES), ("en", EN)):
            section = self._build_section(prefix, GENGAR)
            with self.subTest(prefix=prefix):
                self.assertIn('data-build="defensive"', section)
                self.assertIn(html_lib.escape(lang.t("bd_def_h")), section)
                self.assertIn('<table class="bd-vs">', section)
                self.assertEqual(section.count("<tr>"), 4)
                self.assertIn(html_lib.escape(lang.t("bd_def_col_off")), section)
                self.assertIn(html_lib.escape(lang.t("bd_def_col_def")), section)
                self.assertIn('<p class="bd-verdict">' + ("With Harden" if prefix else "Con Fortaleza"), section)

    def test_species_without_a_defensive_group_never_mentions_it(self) -> None:
        self.assertNotIn(builds.DEFENSIVE, _kinds_by_dex()[SINISTCHA])
        for prefix, words in (("", r"Fortaleza|defensiv"), ("en", r"Harden|defensive")):
            page = self._page(prefix, self._slug(SINISTCHA))
            self.assertNotRegex(self._text(page), words)

    def test_species_without_an_offensive_build_shows_the_defensive_one_as_its_build(self) -> None:
        self.assertEqual(_kinds_by_dex()[CORVISQUIRE], {builds.DEFENSIVE})
        for prefix in ("", "en"):
            page = self._page(prefix, self._slug(CORVISQUIRE))
            with self.subTest(prefix=prefix):
                self.assertNotIn('class="bd-opt', page)
                self.assertNotIn('class="bd-pair', page)
                self.assertIn('data-build="defensive"', page)
                self.assertIn('class="bd-cardlist"', page)
                self.assertNotIn("Ofensiva", self._text(self._build_section(prefix, CORVISQUIRE)))

    def test_special_attacker_text_never_mentions_melee(self) -> None:
        for prefix in ("", "en"):
            page = self._page(prefix, self._slug(GENGAR))
            text = self._text(page) + " ".join(re.findall(r'content="([^"]*)"', page))
            with self.subTest(prefix=prefix):
                self.assertNotRegex(text, r"(?i)cuerpo a cuerpo|melee|dos builds|two builds")


if __name__ == "__main__":
    unittest.main()
