"""La nota de tier S: cifras, condiciones para mostrarla y la distancia de los meteoros frente al juego.

    python3 -m unittest build/test_tier_s_note.py
"""
from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import sitefixture  # noqa: E402
import tier_s_note  # noqa: E402

DATA = ROOT / "data"


def _rows(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _mon(dex: int, tier: str, types: list[str], moves: list[str]) -> dict:
    return {"dex": dex, "types": types, "r": {"tier": tier, "best": "melee"}, "builds": {"melee": {"moves": moves}}}


def _move(mid: str, category: str, rank: int, mtype: str = "steel") -> dict:
    return {"id": mid, "category": category, "rank": rank, "type": mtype, "name": f"{mid} es", "en": {"name": mid}}


GAME = {"count": 2, "dmg": 34, "cd": 1.4, "radius": 54, "knock": 80}
POOL = {"normal": ["tackle"], "steel": ["meteor-mash", "iron-head"], "fire": ["ember"]}


def _fixture(steel_in_s: int, n_s: int = 30, first_physical: str = "meteor-mash",
             learners: tuple[str, ...] = ("steel",)) -> tuple[list[dict], list[dict], dict, dict]:
    entries = []
    for i in range(n_s):
        types = ["steel", "dragon"] if i < steel_in_s else ["fire"]
        moves = ["meteor-mash"] if i < steel_in_s else ["ember"]
        entries.append(_mon(i + 1, "S", types, moves))
    entries.append(_mon(999, "A", ["normal"], ["tackle"]))
    moves = [_move("meteor-mash", "physical", 2), _move(first_physical, "physical", 1), _move("ember", "special", 1, "fire")]
    pool = {"normal": ["tackle"], "fire": ["ember"], **{t: ["meteor-mash"] for t in learners}}
    v3 = {"meteor-mash": {"levels": [dict(GAME, name="Puño Meteoro")]}}
    return entries, moves, v3, pool


class ComputeRules(unittest.TestCase):
    def test_shown_when_steel_is_at_least_half_and_it_is_the_top_physical_move(self) -> None:
        entries, moves, v3, pool = _fixture(steel_in_s=15, first_physical="meteor-mash")
        out = tier_s_note.compute(entries, moves, v3, pool)
        self.assertTrue(out["show"])
        self.assertEqual((out["n"], out["steel"], out["meteor"]), (30, 15, 15))
        self.assertEqual(out["move"]["rank"], 1)

    def test_hidden_when_steel_is_under_half_of_tier_s(self) -> None:
        entries, moves, v3, pool = _fixture(steel_in_s=14)
        self.assertFalse(tier_s_note.compute(entries, moves, v3, pool)["show"])

    def test_hidden_when_meteor_mash_is_not_the_top_physical_move(self) -> None:
        entries, moves, v3, pool = _fixture(steel_in_s=26, first_physical="rock-throw")
        out = tier_s_note.compute(entries, moves, v3, pool)
        self.assertFalse(out["show"])
        self.assertEqual(out["move"]["rank"], 2)

    def test_hidden_when_another_type_can_learn_it(self) -> None:
        entries, moves, v3, pool = _fixture(steel_in_s=26, learners=("steel", "fire"))
        out = tier_s_note.compute(entries, moves, v3, pool)
        self.assertFalse(out["show"])
        self.assertEqual(out["learners"], ["fire", "steel"])

    def test_missing_move_is_an_error_not_a_silent_note(self) -> None:
        entries, moves, v3, pool = _fixture(steel_in_s=26)
        moves = [m for m in moves if m["id"] != "meteor-mash"]
        with self.assertRaises(tier_s_note.TierSError):
            tier_s_note.compute(entries, moves, v3, pool)


class RealData(unittest.TestCase):
    """Las cifras de la nota recalculadas a mano desde los CSV y la Pokédex, sin pasar por catalog.py."""

    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site(need_site=False)
        cls.meta = json.loads((ROOT / "build" / "out" / "meta.json").read_text(encoding="utf8"))["tierS"]

    def test_counts_match_the_raw_tables(self) -> None:
        dex = {p["dex"]: p for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
        builds = {(int(r["dex"]), r["build"]): r["group"].split("+") for r in _rows("species_builds.csv")}
        top = [r for r in _rows("ranking_fase3.csv") if r["tier"] == "S"]
        steel = sum("steel" in dex[int(r["dex"])]["types"] for r in top)
        meteor = sum("meteor-mash" in builds[(int(r["dex"]), r["build"])] for r in top)
        self.assertEqual((self.meta["n"], self.meta["steel"], self.meta["meteor"]), (len(top), steel, meteor))

    def test_physical_rank_and_learners_come_from_the_tables(self) -> None:
        phys = sorted((r for r in _rows("attack_tiers.csv") if r["class"] == "physical"), key=lambda r: int(r["rank"]))
        self.assertEqual(self.meta["move"]["rank"], [r["move_id"] for r in phys].index("meteor-mash") + 1)
        pool = json.loads((DATA / "move_pool.json").read_text(encoding="utf8"))
        self.assertEqual(self.meta["learners"], sorted(t for t, ids in pool.items() if "meteor-mash" in ids))

    def test_game_numbers_come_from_v3_data(self) -> None:
        v3 = json.loads((ROOT / "simulator" / "v3" / "v3_data.json").read_text(encoding="utf8"))["moves"]
        base = v3["meteor-mash"]["levels"][0]
        self.assertEqual(self.meta["stats"], {"count": base["count"], "dmg": base["dmg"], "cd": base["cd"],
                                              "radius": base["radius"], "knock": base["knock"],
                                              "reach": tier_s_note.REACH})

    def test_note_is_hidden_on_the_bounded_ranking(self) -> None:
        # Con el ranking acotado los Acero ya no son la mitad de tier S: la nota no se sostiene y no se enseña.
        self.assertEqual(self.meta["show"], 2 * self.meta["steel"] >= self.meta["n"] and self.meta["show"])


class ReachMatchesTheGame(unittest.TestCase):
    def test_reach_is_the_one_in_combat_js(self) -> None:
        game = tier_s_note.game_reach()
        if game is None:
            self.skipTest("simulator/vendor/pokesurvivor-5a23d49 no está en el repositorio")
        self.assertEqual(tier_s_note.REACH, game)


if __name__ == "__main__":
    unittest.main()
