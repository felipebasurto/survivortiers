"""Las cifras de la página Método salen de los CSV. Estas pruebas comprueban que cuadran entre sí y con las columnas n."""
import csv
import unittest

import method_stats as ms
import regen
import tiers


def _rows(path):
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


class MethodStatsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = ms.compute()

    def test_games_add_up_across_stages(self):
        s = self.stats
        self.assertEqual(s["games"], sum(st["games"] for st in s["stages"]))
        self.assertEqual(s["hours"], sum(st["hours"] for st in s["stages"]))

    def test_each_stage_games_is_rows_times_seeds(self):
        for st in self.stats["stages"]:
            self.assertEqual(st["games"], st["rows"] * st["seeds"], st["id"])

    def test_seeds_match_the_n_column_where_the_csv_has_one(self):
        checks = {
            "start_screen": ms.FIXED / "solo_screen.csv",
            "start_refine": ms.FIXED / "solo_refine.csv",
            "move_duel": ms.FIXED / "solo_contend.csv",
            "start_sweep": ms.FIXED / "g2p2" / "starter_sweep.csv",
            "final": ms.FIXED / "g2p2" / "rank_200.csv",
        }
        seeds = {st["id"]: st["seeds"] for st in self.stats["stages"]}
        for stage, path in checks.items():
            ns = {int(r["n"]) for r in _rows(path)}
            self.assertEqual(ns, {seeds[stage]}, stage)

    def test_group_stages_use_the_pipeline_constants(self):
        seeds = {st["id"]: st["seeds"] for st in self.stats["stages"]}
        self.assertEqual(seeds["group_screen"], regen.SCREEN_SEEDS)
        self.assertEqual(seeds["group_refine"], regen.GROUP_REFINE_SEEDS)

    def test_pipeline_total_is_the_published_six_million(self):
        self.assertEqual(self.stats["games"], 6_429_216)

    def test_histograms_hold_every_pokemon(self):
        self.assertEqual(sum(self.stats["start"]["counts"]), tiers.TOTAL)
        self.assertEqual(sum(self.stats["width"]["counts"]), tiers.TOTAL)

    def test_straddle_counts_are_bounded_by_the_roster(self):
        cuts = self.stats["straddle"]
        self.assertEqual(len(cuts), len(tiers.CUTS) - 1)
        for c in cuts:
            self.assertTrue(0 <= c["count"] <= tiers.TOTAL)
        self.assertLessEqual(self.stats["straddleAny"], tiers.TOTAL)
        self.assertGreaterEqual(self.stats["straddleAny"], max(c["count"] for c in cuts))


if __name__ == "__main__":
    unittest.main()
