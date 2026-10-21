"""Grupos posibles de cada Pokémon (build/builds.py) y las dos builds en la ficha.

    python3 -m unittest build/test_builds.py
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import builds  # noqa: E402
import sitefixture  # noqa: E402
import static_ficha  # noqa: E402
from i18n import EN, ES  # noqa: E402


class Candidates(unittest.TestCase):
    def test_build_kind_follows_the_melee_attacks(self) -> None:
        for dex in (1, 94, 150, 483):
            for group, build in builds.candidates(dex).items():
                attacks = [m for m in group.split("+") if builds._game_moves()[m]["kind"] != "buff"]
                with self.subTest(dex=dex, group=group):
                    self.assertEqual(build == "melee", any(builds._is_melee(a) for a in attacks))

    def test_attack_buff_raises_an_attack_of_the_group(self) -> None:
        self.assertEqual(builds.attack_buffs(["ember", "flamethrower"]), ["nasty-plot"])
        self.assertEqual(builds.attack_buffs(["ember", "meteor-mash"], dragon_dance=False), ["nasty-plot", "swords-dance"])

    def test_every_shape_fills_the_four_slots(self) -> None:
        for group in builds.variants(["ember", "meteor-mash", "rock-throw"]) + builds.variants(["ember", "meteor-mash"]):
            self.assertEqual(len(group.split("+")), builds.picks.BOND_SLOTS, group)


def _b(score: float) -> dict:
    return {"score": score}


class Verdict(unittest.TestCase):
    def test_winner_and_tie(self) -> None:
        self.assertEqual(static_ficha._winner({"melee": _b(10), "ranged": _b(9)}), "melee")
        self.assertIsNone(static_ficha._winner({"melee": _b(10), "ranged": _b(10)}))

    def test_gap_is_said_plainly(self) -> None:
        small = static_ficha._verdict(ES, "ranged", _b(98), _b(100), "melee")
        self.assertIn("Solo un 2 % peor que la build cuerpo a cuerpo.", small)
        large = static_ficha._verdict(EN, "melee", _b(80), _b(100), "ranged")
        self.assertIn("20% below the ranged build.", large)
        self.assertIn("is-best", static_ficha._verdict(ES, "melee", _b(100), _b(80), "melee"))


class FichaBuilds(unittest.TestCase):
    """Las fichas ya generadas (python3 build/render.py) frente a data/species.json."""

    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()
        cls.pairs = json.loads((ROOT / "site" / "data" / "species.json").read_text(encoding="utf8"))["builds"]
        cls.moves = {m["id"]: m for m in json.loads((ROOT / "site" / "data" / "moves.json").read_text(encoding="utf8"))}
        cls.moves.update({m["id"]: m for m in
                          json.loads((ROOT / "site" / "data" / "moves_unranked.json").read_text(encoding="utf8"))})

    def _page(self, prefix: str, dex: int) -> str:
        folder = next((ROOT / "site" / prefix / "pokemon").glob(f"{dex}-*"))
        return (folder / "index.html").read_text(encoding="utf8")

    def test_both_builds_with_the_best_first_and_marked(self) -> None:
        for dex in (1, 94, 150, 354, 483):
            pair = self.pairs[str(dex)]
            for prefix in ("", "en"):
                page = self._page(prefix, dex)
                with self.subTest(dex=dex, prefix=prefix):
                    boxes = re.findall(r'<article class="bd-opt([^"]*)" data-build="(\w+)">', page)
                    self.assertEqual([k for _, k in boxes][0], pair["best"])
                    self.assertEqual(sorted(k for _, k in boxes), ["melee", "ranged"])
                    self.assertEqual([k for cls, k in boxes if "is-best" in cls], [pair["best"]])

    def test_each_build_starts_with_its_first_move(self) -> None:
        for dex in (94, 354):
            for prefix, L in (("", ES), ("en", EN)):
                page = self._page(prefix, dex)
                for kind in ("melee", "ranged"):
                    first = self.moves[self.pairs[str(dex)][kind]["moves"][0]]
                    name = first["en"]["name"] if L.en else first["name"]
                    with self.subTest(dex=dex, prefix=prefix, kind=kind):
                        box = re.search(rf'<article class="bd-opt[^"]*" data-build="{kind}">.*?</article>', page, re.S)
                        rows = re.findall(r'<li class="bd-row[^"]*">.*?</li>', box.group(0), re.S)
                        self.assertEqual(len(rows), len(self.pairs[str(dex)][kind]["moves"]))
                        self.assertIn("is-start", rows[0])
                        self.assertIn(f'<span class="bd-nm">{name}</span>', rows[0])
                        self.assertEqual(sum("is-start" in r for r in rows), 1)

    def test_every_move_row_has_its_game_icon(self) -> None:
        for dex, prefix, up in ((94, "", "../../"), (354, "en", "../../../")):
            page = self._page(prefix, dex)
            ids = [m for k in ("melee", "ranged") for m in self.pairs[str(dex)][k]["moves"]]
            srcs = re.findall(r'<span class="bd-ico"><img src="([^"]+)"', page)
            with self.subTest(dex=dex, prefix=prefix):
                self.assertEqual(sorted(srcs), sorted(f"{up}img/moves/{m}.svg" for m in ids))
                for m in ids:
                    self.assertTrue((ROOT / "site" / "img" / "moves" / f"{m}.svg").is_file(), m)

    def test_boosts_have_no_range_tag(self) -> None:
        page = self._page("", 483)
        for row in re.findall(r'<li class="bd-row is-buff[^"]*">.*?</li>', page, re.S):
            self.assertNotIn("rng-tag", row)


if __name__ == "__main__":
    unittest.main()
