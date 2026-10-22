from __future__ import annotations

import json
import unittest
from pathlib import Path

from build.laboratory_export import _same_provenance, export_attacks, export_ranking


ROOT = Path(__file__).resolve().parents[1]
GAME = json.loads((ROOT / "simulator/data/game.json").read_text())


def lab_doc() -> dict:
    from build.lab_contract import SCENARIOS, PHASES
    rows = []
    for mid, early, late in (("water-gun", 3.0, 3.4), ("bubble", 2.5, 3.0)):
        scenarios = [{"id": f"{shape}-{count}-{phase}", "phase": phase,
                      "level": 1 if phase == "initial" else 5, "seeds": [11014, 25025],
                      "damagePerSecond": early if phase == "initial" else late,
                      "killsPerMinute": 8.0}
                     for shape, count in SCENARIOS for phase in PHASES]
        rows.append({"id": mid, "score": (early + late) / 2, "earlyScore": early,
                     "lateScore": late, "scenarios": scenarios})
    return {"schema": 1, "kind": "attack-lab-results", "complete": True,
            "policyVersion": "attack-lab-v1", "scope": "all-supported-attacks", "partialScope": False,
            "secondsPerScenario": 60, "gameCommit": GAME["gameCommit"],
            "engineFingerprint": "engine-a", "moves": rows}


def ranking_doc() -> dict:
    return {
        "schema": 1, "kind": "bounded-ranking-results", "complete": True,
        "rankingReady": False, "gameCommit": GAME["gameCommit"],
        "engineFingerprint": "engine-a", "policyVersion": "bounded-ranking-v2",
        "policyHash": "policy-hash", "planHash": "plan-hash",
        "seedSets": {"A": [1001, 1002], "B": list(range(1101, 1109)), "D": list(range(3001, 3017)),
                     "screening": list(range(1001, 1003)) + list(range(1101, 1109)),
                     "confirmation": list(range(3001, 3017))},
        "winners": [{
            "dex": 54, "status": "best_observed", "winnerConfirmed": True,
            "configuration": {"id": "psyduck-water-gun", "build": "ranged", "branch": "optimized_no_tm",
                               "group": ["water-gun"], "ability": "damp", "nature": "hardy", "tms": []},
            "meanSurvival": 21.5, "meanDamagePerSecond": 4.25, "meanKills": 6.5,
            "pairedConfirmation": {"seeds": list(range(3001, 3017)), "n": 16, "delta": 0.3},
        }],
        "controls": [], "unavailable": [],
    }


class LaboratoryExportTests(unittest.TestCase):
    def test_attacks_export_complete_move_rows_without_row_complete_field(self) -> None:
        out = export_attacks(lab_doc())
        self.assertEqual(out["kind"], "attack-lab-export")
        self.assertEqual([row["id"] for row in out["moves"]], ["water-gun", "bubble"])
        self.assertEqual(out["moves"][0]["scenarios"][0]["damagePerSecond"], 3.0)
        self.assertFalse(out["rankingReady"])

    def test_attacks_reject_global_or_explicit_row_incompletion(self) -> None:
        data = lab_doc(); data["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            export_attacks(data)
        data = lab_doc(); data["moves"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "move water-gun is incomplete"):
            export_attacks(data)

    def test_ranking_preserves_metrics_and_validated_seed_objects(self) -> None:
        ranking = ranking_doc()
        _same_provenance(lab_doc(), ranking, GAME)
        out = export_ranking(ranking, GAME)
        self.assertEqual(out["ranking_method"]["status"], "diagnostic_only")
        self.assertEqual(out["experiment"]["seed_sets"]["screening"]["count"], 10)
        self.assertEqual(out["experiment"]["seed_sets"]["confirmation"]["count"], 16)
        # The paired confirmation was played on the independent D seeds, not on the B screening seeds.
        self.assertEqual(out["experiment"]["seed_sets"]["paired_confirmation"],
                         out["experiment"]["seed_sets"]["confirmation"])
        self.assertEqual(out["results"][0]["score"]["version"], "bounded-ranking-v2")
        self.assertEqual(out["results"][0]["score"]["metrics"]["damagePerSecond"], 4.25)
        self.assertEqual(out["results"][0]["score"]["metrics"]["meanKills"], 6.5)
        self.assertEqual(out["results"][0]["paired_confirmation"]["delta"], 0.3)

    def test_rejects_stale_and_incomplete_ranking(self) -> None:
        lab, ranking = lab_doc(), ranking_doc()
        ranking["engineFingerprint"] = "stale"
        with self.assertRaisesRegex(ValueError, "engine fingerprint mismatch"):
            _same_provenance(lab, ranking, GAME)
        ranking = ranking_doc(); ranking["complete"] = False
        with self.assertRaisesRegex(ValueError, "ranking results are incomplete"):
            export_ranking(ranking, GAME)
        ranking = ranking_doc(); ranking["winners"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "winner for dex 54 is incomplete"):
            export_ranking(ranking, GAME)

    def test_rejects_truthy_confirmation_strings(self):
        ranking = ranking_doc()
        ranking["winners"][0]["winnerConfirmed"] = "false"
        with self.assertRaisesRegex(ValueError, "winnerConfirmed"):
            export_ranking(ranking, GAME)

    def test_rejects_missing_scenarios_and_invalid_metrics(self):
        data = lab_doc()
        data["moves"][0]["scenarios"].pop()
        with self.assertRaises(ValueError):
            export_attacks(data)
        for value in (True, -1, float("nan")):
            data = lab_doc()
            data["moves"][0]["scenarios"][0]["damagePerSecond"] = value
            with self.assertRaises(ValueError):
                export_attacks(data)

    def test_rejects_malformed_row_completeness(self):
        data = lab_doc()
        data["moves"][0]["complete"] = "true"
        with self.assertRaises(ValueError):
            export_attacks(data)


if __name__ == "__main__":
    unittest.main()
