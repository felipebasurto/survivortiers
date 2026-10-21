"""Test-only production record fixture; never publish this fixture as a ranking."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from build.sim_export import ExportError, build_web_export, parse_ability_effects, validate_build_metadata, _renderable_winner
from build.sim_cards import render_cards


ROOT = Path(__file__).resolve().parents[1]
GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
METADATA = json.loads((ROOT / "simulator/data/build-metadata.json").read_text(encoding="utf8"))


def production_fixture() -> dict:
    winners = []
    for style in ("melee", "ranged"):
        for role in ("base", "aggro", "coverage", "both"):
            for branch in ("optimized_tm", "optimized_no_tm"):
                if (style, role, branch) == ("ranged", "both", "optimized_no_tm"):
                    continue  # Explicit policy-unavailable stratum below.
                optimized = branch == "optimized_tm"
                group = ["thunderbolt", "discharge", "agility", "harden"] if optimized else ["thunder-shock", "discharge", "agility", "harden"]
                config_id = f"dex25|{style}|{role}|{branch}"
                variant_id = f"{style}:{role}:{branch}"
                winners.append({
                    "configurationId": config_id, "variantId": variant_id, "dex": 25,
                    "status": "tied_best" if (style, role) == ("melee", "coverage") else "best_observed",
                    "winnerConfirmed": True,
                    "confidence": {
                        "method": "paired student-t 95% descriptive intervals; no multiple-comparison claim",
                        "survival": {"n": 16, "meanDifference": 12.3, "lower": -4.2, "upper": 28.8},
                        "contactDamage": {"n": 16, "meanDifference": -3.1, "lower": -5.0, "upper": -1.2},
                    },
                    "config": {"group": group, "tms": ["thunderbolt"] if optimized else [],
                               "secondStart": "discharge", "nature": "adamant",
                               "ability": "lightning-rod" if style == "melee" and role == "base" and branch == "optimized_tm" else "static",
                               "build": style, "role": role, "branch": branch},
                    "summary": {"candidateSurvivalMean": 900.0, "damage": 42000.0,
                                "contactDamage": 80.0, "contactSeconds": 12.0, "trappedSeconds": 1.0},
                    "paired": [{"seed": 1000 + i, "candidate": {"survivalSeconds": 900.0},
                                "control": {"survivalSeconds": 887.7}} for i in range(16)],
                })
    control = {
        "configurationId": "dex25|control-no-tm", "variantId": "melee:base:control_no_tm", "dex": 25,
        "status": "tied_best", "winnerConfirmed": True,
        "config": {"group": ["thunder-shock", "quick-attack"], "tms": [], "nature": "hardy",
                   "ability": "static", "build": "melee", "role": "base", "branch": "control_no_tm"},
        "summary": {"survivalSeconds": 887.7, "damage": 40000.0},
    }
    unavailable = [{"dex": 25, "variantId": "ranged:both:optimized_no_tm", "reason": "No safe confirmed candidate."}]
    return {
        "schema": 1, "policyVersion": "policy-1", "policyHash": "sha256:policy", "planHash": "sha256:plan",
        "provenance": {"gameCommit": GAME["gameCommit"], "engineFingerprint": "sha256:engine"},
        "seedSets": {"screening": list(range(16)), "confirmation": list(range(1000, 1016))},
        "limits": {"fixture": True}, "rankingReady": False, "winners": winners + [control],
        "unavailable": unavailable,
    }


class SimExportTests(unittest.TestCase):
    def test_real_data_fixture_exports_valid_json_and_renderable_feature_cards(self):
        fixture = production_fixture()
        output = build_web_export(fixture, GAME, METADATA["ability_effects"], metadata=METADATA)
        self.assertEqual(output["provenance"]["game_commit"], GAME["gameCommit"])
        self.assertEqual(len(output["results"]), 15)
        self.assertEqual(len(output["unavailable_variants"]), 1)
        card = render_cards(output, 25)
        for text in ("Aggro", "Cobertura", "Los ataques de tipo Eléctrico", "Naturaleza", "sube Ataque", "baja Ataque especial",
                     "MT necesarias", "840 monedas", "Movimientos iniciales", "requiere moves (1500 monedas)",
                     "IC descriptivo", "empate", "Cápsula Habilidad Oculta (5000 monedas)",
                     "Alternativa sin MT evaluada", "Build no disponible"):
            self.assertIn(text, card)
        self.assertEqual(len(METADATA["ability_effects"]), len(GAME["abilities"]))
        self.assertTrue(all(row.get("effect") or row["kind"] == "primary_type_fallback"
                            for row in METADATA["ability_effects"].values()))

    def test_rejects_wrong_game_commit_and_unknown_variant_records(self):
        fixture = production_fixture()
        fixture["provenance"]["gameCommit"] = "b" * 40
        with self.assertRaisesRegex(ExportError, "does not match"):
            build_web_export(fixture, GAME, {"static": "effect"})

    def test_parser_resolves_special_and_generic_plus_effects(self):
        source = """G.AbilityFX = (() => {\n  const FX = {\n    'static': contact((pl, e) => null, 'Quien le golpea se frena.'),\n    'iron-fist': byName(/punch/, 'los puñetazos', 1.25),\n    'overcoat': { d: 'Recibe un 5 % menos de daño especial.', plus: true },\n  };\n})();"""
        effects = parse_ability_effects(source)
        self.assertEqual(effects["static"]["effect"], "Quien le golpea se frena.")
        self.assertEqual(effects["iron-fist"]["effect"], "+25 % de daño con los puñetazos.")
        self.assertTrue(effects["overcoat"]["plus_type_fallback"])

    def test_source_backed_artifact_has_full_catalog_and_acquisition_metadata(self):
        validate_build_metadata(METADATA, GAME)
        self.assertEqual(METADATA["source_commit"], "ce5785313b0205af8b9477423f64b0a7b7039dcd")
        self.assertEqual(METADATA["shop_items"]["caph"]["price"], 5000)
        self.assertEqual(METADATA["upgrades"]["start2"]["price"], 400)
        self.assertEqual(METADATA["upgrades"]["start2"]["requires"], "moves")
        self.assertEqual(METADATA["ability_effects"]["air-lock"]["kind"], "primary_type_fallback")
        self.assertTrue(METADATA["ability_effects"]["zen-mode"]["plus_type_fallback"])

    def test_custom_plus_and_primary_type_fallback_render_from_catalog(self):
        capsules = {key: METADATA["shop_items"][key] for key in ("cap", "caph")}
        role_variant = {"id": "aggro-baseline__coverage-baseline", "aggro": "baseline", "coverage": "baseline"}
        base = {"configurationId": "source-check", "dex": 555,
                "summary": {"survival": 10}, "confidence": {}, "paired": []}
        plus = _renderable_winner({**base, "dex": 555},
            {"group": ["flame-wheel"], "tms": [], "secondStart": None, "nature": "adamant",
             "ability": "zen-mode", "build": "melee", "role": "base"}, role_variant, "optimized",
            GAME, METADATA["ability_effects"], capsules, "game.json", "ability-fx.js", "shop.js", METADATA["shop_items"])
        self.assertEqual(plus["build"]["ability_slot"], "hidden")
        self.assertIn("Además, +8 % de daño con movimientos de tipo Fuego", plus["build"]["ability"]["effect"])
        self.assertIn("Modo Daruma", plus["build"]["ability"]["effect"])
        fallback = _renderable_winner({**base, "dex": 384},
            {"group": ["dragon-rage"], "tms": [], "secondStart": None, "nature": "adamant",
             "ability": "air-lock", "build": "ranged", "role": "base"}, role_variant, "optimized",
            GAME, METADATA["ability_effects"], capsules, "game.json", "ability-fx.js", "shop.js", METADATA["shop_items"])
        self.assertEqual(fallback["build"]["ability"]["effect_kind"], "generic_type_fallback")
        self.assertIn("tipo Dragón", fallback["build"]["ability"]["effect"])

    def test_current_production_record_shape_exports_without_manual_relabeling(self):
        source = production_fixture()
        winners = []
        for row in source["winners"]:
            if row["config"]["branch"] == "control_no_tm":
                continue  # controls are paired into each measured candidate record
            converted = dict(row)
            config = converted.pop("config")
            converted["configuration"] = {"id": converted["configurationId"], **config}
            converted.pop("configurationId")
            confidence = converted.pop("confidence")
            paired = converted.pop("paired")
            converted["pairedConfirmation"] = {
                "n": 16,
                "survivalSeconds": {"n": 16, "mean": 12.3, "lower": -4.2, "upper": 28.8},
                "contactDamagePerMinute": {"n": 16, "mean": -3.1, "lower": -5.0, "upper": -1.2},
                "contactFraction": {"n": 16, "mean": -0.01, "lower": -0.02, "upper": 0.0},
                "trappedFraction": {"n": 16, "mean": 0.0, "lower": 0.0, "upper": 0.0},
                "meanDelta": {"survivalSeconds": 12.3, "contactDamagePerMinute": -3.1,
                              "contactFraction": -0.01, "trappedFraction": 0.0},
                "perSeed": [{"seed": item["seed"], "candidate": item["candidate"], "control": item["control"]}
                            for item in paired],
            }
            converted.pop("summary", None)
            winners.append(converted)
        current = {"schema": 1, "policyVersion": "policy-1", "manifestHash": "sha256:manifest",
                   "planHash": "sha256:plan", "gameCommit": GAME["gameCommit"],
                   "engineFingerprint": "sha256:engine", "rankingReady": False,
                   "observations": [{"stage": stage, "seed": seed} for stage, values in
                                    (("screening", range(16)), ("confirmation", range(1000, 1016))) for seed in values],
                   "winners": winners, "unavailable": source["unavailable"]}
        output = build_web_export(current, GAME, METADATA["ability_effects"], metadata=METADATA)
        self.assertEqual(len(output["results"]), 15)
        card = render_cards(output, 25)
        self.assertIn("contactDamagePerMinute", card)
        self.assertIn("IC descriptivo", card)


if __name__ == "__main__":
    unittest.main()
