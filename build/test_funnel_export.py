import json
import unittest
from pathlib import Path

from build.funnel_export import export_document, legal_initial


GAME = json.loads((Path(__file__).resolve().parents[1] / "simulator/data/game.json").read_text())


def _species(dex: int) -> dict:
    return next(row for row in GAME["dex"] if row["dex"] == dex)


def _funnel(dex: int, safe: bool) -> dict:
    species = _species(dex)
    ability = next(item for item in species["abilities"] if item)
    group = [species["start"]]
    config = {
        "id": f"funnel|dex:{dex}|branch:optimized_no_tm",
        "group": group,
        "tms": [],
        "tmCost": 0,
        "secondStart": None,
        "nature": "hardy",
        "ability": ability,
        "build": "melee",
        "role": "base",
        "branch": "optimized_no_tm",
    }
    return {
        "schema": 1,
        "kind": "funnel-results",
        "rankingReady": False,
        "gameCommit": GAME["gameCommit"],
        "engineFingerprint": "test-fingerprint",
        "policyVersion": "survivortiers-funnel-v1",
        "policyHash": "abc",
        "planHash": "def",
        "seedSets": {"screening": [1001, 1002], "confirmation": [3001, 3002]},
        "winners": [{
            "dex": dex,
            "status": "best_observed" if safe else "no_safe_candidate",
            "winnerConfirmed": safe,
            "meanSurvival": 120.0,
            "configuration": config,
        }],
        "controls": [{
            "dex": dex,
            "meanSurvival": 80.0,
            "configuration": {
                **config,
                "id": f"control|dex:{dex}",
                "branch": "control_no_tm",
            },
        }],
        "unavailable": [
            {"dex": dex, "variantId": "ranged:base:optimized_no_tm", "reason": "no legal base-role group in the move beam"},
            {"dex": dex, "variantId": "melee:base:optimized_tm", "reason": "species has no legal TM"},
            {"dex": dex, "variantId": "ranged:base:optimized_tm", "reason": "species has no legal TM"},
            {"dex": dex, "variantId": "melee:aggro:optimized_no_tm", "reason": "funnel v1 measures the base role only"},
        ],
    }


class FunnelExportTests(unittest.TestCase):
    def test_safe_winner_passes_the_web_contract(self) -> None:
        document = export_document(_funnel(132, True), GAME)
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["ranking_method"]["status"], "diagnostic_only")
        self.assertEqual(document["optimized_potential"], [])
        self.assertEqual(len(document["results"]), 1)
        self.assertTrue(document["results"][0]["winner_confirmed"])
        self.assertEqual(document["results"][0]["pokemon"]["slug"], "ditto")

    def test_unsafe_winner_publishes_the_measured_control(self) -> None:
        document = export_document(_funnel(132, False), GAME)
        self.assertEqual(len(document["results"]), 1)
        self.assertEqual(document["results"][0]["build"]["availability"], "no_tm")
        self.assertEqual(document["results"][0]["score"]["metrics"]["survivalSeconds"], 80.0)
        covered = {(row["dex"], row["style"], row["availability"]) for row in document["unavailable_variants"]}
        self.assertIn((132, "ranged", "optimized"), covered)
        self.assertNotIn((132, "melee", "no_tm"), covered)

    def test_psyduck_stock_confusion_and_a_taught_tm(self) -> None:
        psyduck = _species(54)
        self.assertEqual(psyduck["start"], "confusion")
        self.assertEqual(legal_initial(GAME, psyduck, ["confusion"], set()), "confusion")
        self.assertEqual(legal_initial(GAME, psyduck, ["tackle"], set()), "tackle")
        self.assertIsNone(legal_initial(GAME, psyduck, ["ice-beam"], set()))
        self.assertEqual(legal_initial(GAME, psyduck, ["ice-beam"], {"ice-beam"}), "ice-beam")
        self.assertIsNone(legal_initial(GAME, psyduck, ["ember"], set()))
        self.assertIsNone(legal_initial(GAME, psyduck, ["swords-dance"], {"swords-dance"}))
        document = export_document(_funnel(54, True), GAME)
        self.assertEqual(document["results"][0]["build"]["initial_attacks"], ["confusion"])
