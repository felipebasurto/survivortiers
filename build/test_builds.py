"""Grupos posibles de cada Pokémon (build/builds.py) y las mejores builds en la ficha.

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


class FichaBuilds(unittest.TestCase):
    """Las fichas ya generadas (python3 build/render.py) frente a data/bounded_ranking.json."""

    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()
        cls.bounded = json.loads((ROOT / "data" / "bounded_ranking.json").read_text(encoding="utf8"))["species"]

    def _page(self, prefix: str, dex: int) -> str:
        folder = next((ROOT / "site" / prefix / "pokemon").glob(f"{dex}-*"))
        return (folder / "index.html").read_text(encoding="utf8")

    def test_builds_come_first_with_the_longest_survival_first(self) -> None:
        for dex in (1, 94, 150, 354, 483, 921):
            rows = self.bounded[str(dex)]
            best = max((s for s in ("melee", "ranged") if f"{s}|no_tm" in rows),
                       key=lambda s: rows[f"{s}|no_tm"]["survival"])
            for prefix in ("", "en"):
                page = self._page(prefix, dex)
                with self.subTest(dex=dex, prefix=prefix):
                    self.assertLess(page.index('id="build"'), page.index('id="porque"'))
                    cards = re.findall(r'<li class="bx-card" data-build="(\w+)">(.*?)</li></ul><p', page, re.S)
                    self.assertEqual(cards[0][0], best)
                    for _, body in cards:
                        self.assertTrue(1 <= len(re.findall(r'class="bx-chip[" ]', body)) <= 4)

    def test_no_provenance_on_the_ficha(self) -> None:
        page = self._page("", 614)
        for word in ("sha256", "Runpod", "semillas", "estrato", "bounded-ranking", "candidatas"):
            self.assertNotIn(word, page)


if __name__ == "__main__":
    unittest.main()
