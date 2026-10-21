from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from build import sim_results


def fixture() -> dict:
    variants = [
        {"id": "aggro-low__coverage-low", "aggro": "low", "coverage": "low"},
        {"id": "aggro-low__coverage-high", "aggro": "low", "coverage": "high"},
        {"id": "aggro-high__coverage-low", "aggro": "high", "coverage": "low"},
        {"id": "aggro-high__coverage-high", "aggro": "high", "coverage": "high"},
    ]
    seed_ids = {"screening": list(range(16)), "confirmation": list(range(1000, 1128))}
    seed_sets = {}
    for stage, ids in seed_ids.items():
        digest = "sha256:" + hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        seed_sets[stage] = {"ids": ids, "count": len(ids), "hash": digest}
    rows = []
    for style, availability in ((s, a) for s in ("melee", "ranged") for a in ("optimized", "no_tm")):
        for v in variants:
            bid = f"pikachu-{style}-{availability}-{v['id']}"
            attacks = ([{"id": "thunderbolt", "position": 1}, {"id": "quick-attack", "position": 2}]
                       if availability == "optimized" else [{"id": "thunder-shock", "position": 1}])
            build = {
                "id": bid, "style": style, "availability": availability,
                "attacks": attacks,
                "ability": {"id": "static", "source": "simulator/data/game.json#/abilities/static"},
                "nature": {"id": "adamant", "source": "simulator/data/game.json#/natures/adamant"},
                "tm_requirements": ([{"id": "thunderbolt", "source": "simulator/data/game.json#/tmPrices/thunderbolt"}]
                                    if availability == "optimized" else []),
                "initial_attacks": [attacks[0]["id"]],
            }
            if availability == "optimized":
                build["no_tm_alternative"] = {
                    "build_id": f"pikachu-{style}-no_tm-{v['id']}", "attacks": ["thunder-shock"]
                }
            rows.append({
                "pokemon": {"dex": 25, "slug": "pikachu"}, "build": build,
                "variant": v, "status": "confirmed", "winner_confirmed": True,
                "confirmation_seed_set": {"count": 128, "hash": seed_sets["confirmation"]["hash"]},
                "score": {"version": "metrics-1", "metrics": {"survival_seconds": 1800, "damage": 42000}},
            })
    return {
        "schema_version": 1,
        "provenance": {"game_commit": "a" * 40, "engine_fingerprint": "sha256:engine", "policy_version": "policy-1"},
        "experiment": {
            "score_version": "metrics-1",
            "seed_sets": seed_sets, "pokemon_dexes": [25],
            "axes": {"aggro": ["low", "high"], "coverage": ["low", "high"]}, "expected_variants": variants,
        },
        "results": rows, "unavailable_cohorts": [],
        "ranking_method": {"id": "diagnostic", "status": "diagnostic_only"},
        "optimized_potential": [],
    }


class SimResultsContractTests(unittest.TestCase):
    def test_accepts_complete_versioned_diagnostic_export(self):
        data = fixture()
        self.assertIs(sim_results.validate_results(data), data)

    def test_rejects_missing_variant_in_cohort(self):
        data = fixture()
        data["results"].pop()
        with self.assertRaisesRegex(sim_results.ResultContractError, "missing variants"):
            sim_results.validate_results(data)

    def test_rejects_missing_sources_and_tm_alternative(self):
        data = fixture()
        data["results"][0]["build"]["ability"].pop("source")
        data["results"][0]["build"]["no_tm_alternative"] = None
        with self.assertRaisesRegex(sim_results.ResultContractError, "ability needs an id and source"):
            sim_results.validate_results(data)

    def test_rejects_mixed_confirmation_seeds_and_score_versions(self):
        data = fixture()
        data["results"][1]["confirmation_seed_set"]["hash"] = "sha256:other"
        with self.assertRaisesRegex(sim_results.ResultContractError, "confirmation_seed_set"):
            sim_results.validate_results(data)
        data = fixture()
        data["results"][1]["score"]["version"] = "metrics-2"
        with self.assertRaisesRegex(sim_results.ResultContractError, "score.version"):
            sim_results.validate_results(data)

    def test_rejects_reusing_screening_seeds_for_confirmation(self):
        data = fixture()
        data["experiment"]["seed_sets"]["confirmation"]["ids"] = list(range(16))
        data["experiment"]["seed_sets"]["confirmation"]["count"] = 16
        with self.assertRaisesRegex(sim_results.ResultContractError, "disjoint"):
            sim_results.validate_results(data)

    def test_rejects_placeholder_unconfirmed_and_uncalibrated_rank_claims(self):
        data = fixture()
        data["results"][0]["status"] = "screening"
        data["ranking_method"] = {"id": "rank", "status": "calibrated"}
        with self.assertRaisesRegex(sim_results.ResultContractError, "not confirmed"):
            sim_results.validate_results(data)
        data = fixture()
        data["optimized_potential"] = [{"dex": 25, "build_id": "a", "label": "optimized potential", "status": "confirmed"}]
        with self.assertRaisesRegex(sim_results.ResultContractError, "diagnostic_only"):
            sim_results.validate_results(data)

    def test_checks_ability_nature_tm_catalogs_against_game_data(self):
        data = fixture()
        game = json.loads((Path(__file__).resolve().parents[1] / "simulator/data/game.json").read_text())
        data["provenance"]["game_commit"] = game["gameCommit"]
        # Thunderbolt is a legal purchased TM and may be selected as the first move.
        self.assertEqual(data["results"][0]["build"]["initial_attacks"], ["thunderbolt"])
        sim_results.validate_results(data, game)
        bad = copy.deepcopy(game)
        bad["tmPrices"] = {}
        with self.assertRaisesRegex(sim_results.ResultContractError, "TM absent"):
            sim_results.validate_results(data, bad)

    def test_rejects_missing_cohort_and_dangling_no_tm_reference(self):
        data = fixture()
        data["results"][0]["build"]["no_tm_alternative"]["build_id"] = "dangling"
        with self.assertRaisesRegex(sim_results.ResultContractError, "no matching measured no-TM"):
            sim_results.validate_results(data)
        data = fixture()
        data["results"] = [r for r in data["results"] if not (r["build"]["style"] == "ranged" and r["build"]["availability"] == "no_tm")]
        with self.assertRaisesRegex(sim_results.ResultContractError, "must be available in results or declared unavailable"):
            sim_results.validate_results(data)

    def test_rejects_illegal_species_ability_or_tm_teaching(self):
        data = fixture()
        game = json.loads((Path(__file__).resolve().parents[1] / "simulator/data/game.json").read_text())
        data["provenance"]["game_commit"] = game["gameCommit"]
        data["results"][0]["build"]["ability"]["id"] = "overgrow"
        with self.assertRaisesRegex(sim_results.ResultContractError, "not legal for this species"):
            sim_results.validate_results(data, game)

    def test_rejects_off_type_native_start_and_incompatible_extra_tm(self):
        game = json.loads((Path(__file__).resolve().parents[1] / "simulator/data/game.json").read_text())
        data = fixture()
        data["provenance"]["game_commit"] = game["gameCommit"]
        data["results"][0]["build"]["initial_attacks"] = ["quick-attack"]
        with self.assertRaisesRegex(sim_results.ResultContractError, "not a legal native start choice"):
            sim_results.validate_results(data, game)
        data = fixture()
        data["provenance"]["game_commit"] = game["gameCommit"]
        data["results"][0]["build"]["tm_requirements"].append(
            {"id": "flamethrower", "source": "simulator/data/game.json#/tmPrices/flamethrower"}
        )
        with self.assertRaisesRegex(sim_results.ResultContractError, "not compatible with this species"):
            sim_results.validate_results(data, game)

    def test_tm_buff_cannot_be_a_starting_attack(self):
        game = json.loads((Path(__file__).resolve().parents[1] / "simulator/data/game.json").read_text())
        data = fixture()
        data["provenance"]["game_commit"] = game["gameCommit"]
        build = data["results"][0]["build"]
        build["attacks"][0]["id"] = "swords-dance"
        build["initial_attacks"] = ["swords-dance"]
        build["tm_requirements"] = [{"id": "swords-dance", "source": "simulator/data/game.json#/tmPrices/swords-dance"}]
        with self.assertRaisesRegex(sim_results.ResultContractError, "attacks, not buffs"):
            sim_results.validate_results(data, game)

    def test_malformed_initial_attacks_raise_contract_error(self):
        data = fixture()
        data["results"][0]["build"]["initial_attacks"] = "thunderbolt"
        with self.assertRaisesRegex(sim_results.ResultContractError, "initial_attacks must list"):
            sim_results.validate_results(data)

    def test_rejects_unconfirmed_winner_and_overfull_or_duplicate_slots(self):
        data = fixture()
        data["results"][0].pop("winner_confirmed")
        with self.assertRaisesRegex(sim_results.ResultContractError, "not confirmed"):
            sim_results.validate_results(data)
        data = fixture()
        data["results"][0]["build"]["attacks"] = [
            {"id": "thunderbolt", "position": i} for i in range(1, 6)
        ]
        with self.assertRaisesRegex(sim_results.ResultContractError, "one to four attacks"):
            sim_results.validate_results(data)


if __name__ == "__main__":
    unittest.main()
