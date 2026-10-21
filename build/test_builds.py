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
import coverage  # noqa: E402
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


class Coverage(unittest.TestCase):
    def test_counts_follow_the_game_chart(self) -> None:
        normal = coverage.of_types(["normal"])
        self.assertEqual(normal["good"], 0)  # Normal no es superefectivo contra nada
        self.assertEqual(normal["n"], len(coverage.enemies()))
        both = coverage.of_types(["normal", "fighting"])
        self.assertLessEqual(both["resist"], normal["resist"])
        self.assertTrue(set(both["resist_by"]) <= set(coverage.TYPES))


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
                        rows = re.findall(r'<li class="bd-row[^"]*">.*?</li>', box.group(0).split("<details", 1)[0], re.S)
                        self.assertEqual(len(rows), len(self.pairs[str(dex)][kind]["moves"]))
                        self.assertIn("is-start", rows[0])
                        self.assertIn(f'<span class="bd-nm">{name}</span>', rows[0])
                        self.assertEqual(sum("is-start" in r for r in rows), 1)

    def test_every_move_row_has_its_game_icon(self) -> None:
        for dex, prefix, up in ((94, "", "../../"), (354, "en", "../../../")):
            page = re.sub(r'<details class="bd-alt".*?</details>', "", self._page(prefix, dex), flags=re.S)
            ids = [m for k in ("melee", "ranged") for m in self.pairs[str(dex)][k]["moves"]]
            srcs = re.findall(r'<span class="bd-ico"><img src="([^"]+)"', page)
            with self.subTest(dex=dex, prefix=prefix):
                self.assertEqual(sorted(srcs), sorted(f"{up}img/moves/{m}.svg" for m in ids))
                for m in ids:
                    self.assertTrue((ROOT / "site" / "img" / "moves" / f"{m}.svg").is_file(), m)

    def test_each_build_says_its_coverage_and_move_types(self) -> None:
        for dex in (6, 94, 150):
            pair = self.pairs[str(dex)]
            page = self._page("", dex)
            for kind in ("melee", "ranged"):
                box = re.search(rf'<article class="bd-opt[^"]*" data-build="{kind}">.*?</article>', page, re.S).group(0)
                main = box.split('<details', 1)[0]
                cov = coverage.of_build(pair[kind]["moves"])
                with self.subTest(dex=dex, kind=kind):
                    self.assertIn(f"Pega bien a {cov['good']} de los {len(coverage.enemies())} Pokémon", main)
                    attacks = [m for m in pair[kind]["moves"] if self.moves[m]["kind"] != "buff"]
                    self.assertEqual(main.count('<span class="bd-type">'), len(attacks))

    def test_own_type_bonus_only_for_single_type(self) -> None:
        self.assertIn("bd-mono", self._page("", 150))  # Mewtwo, Psíquico: Confusión es de su tipo
        self.assertNotIn("bd-mono", self._page("", 6))  # Charizard, Fuego/Volador

    def test_variants_change_what_they_say(self) -> None:
        import picks
        seen = set()
        entries = {str(e["dex"]): e for e in json.loads((ROOT / "build" / "out" / "pokemon.json").read_text(encoding="utf8"))}
        for dex, e in entries.items():
            for kind, b in e["builds"].items():
                for v, alt in b.get("alt", {}).items():
                    seen.add(v)
                    with self.subTest(dex=dex, kind=kind, variant=v):
                        self.assertNotEqual(alt["moves"], b["moves"])
                        self.assertEqual(builds._kind(picks.split_group("+".join(alt["moves"]))[0]), kind)
                        if v == "aggro":
                            self.assertIsNotNone(picks.split_group("+".join(b["moves"]))[2])
                            self.assertIsNone(picks.split_group("+".join(alt["moves"]))[2])
                        else:
                            self.assertLessEqual(2 * alt["cover"]["resist"], b["cover"]["resist"])
        self.assertEqual(seen, {"aggro", "cover"})
        page = self._page("", 4)  # Charmander: las dos variantes en su build a distancia
        self.assertEqual(re.findall(r'<details class="bd-alt" data-alt="(\w+)">', page)[:2], ["aggro", "cover"])

    def test_boosts_have_no_range_tag(self) -> None:
        page = self._page("", 483)
        for row in re.findall(r'<li class="bd-row is-buff[^"]*">.*?</li>', page, re.S):
            self.assertNotIn("rng-tag", row)


if __name__ == "__main__":
    unittest.main()
