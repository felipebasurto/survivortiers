"""Exercise the supported commands and exporter as a user would, on short scenes."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "simulator"
BINARY = Path(os.environ.get("POKESIM_TEST_BINARY", SIM / "sim-rs/target/release/pokesim"))


@unittest.skipUnless(BINARY.is_file(), "build the release simulator to run CLI integration")
class BoundedCliTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([str(BINARY), *map(str, args)], cwd=SIM, text=True,
                              capture_output=True, check=True)

    def test_lab_to_survival_export_and_resume(self):
        from build.laboratory_export import _same_provenance, export_attacks, export_ranking
        from build.sim_results import validate_results
        game = json.loads((SIM / "data/game.json").read_text())
        with tempfile.TemporaryDirectory(prefix="survivortiers-cli-") as tmp:
            root = Path(tmp)
            lab_path, plan, output = (root / name for name in ("lab.json", "plan.json", "results.json"))
            cache = root / "matches"
            self.command("attack-lab", "run", lab_path, root / "lab-cache", 2, 0.2)
            guide = root / "lab-with-synergies.json"
            self.command("synergy-lab", "run", lab_path, guide, root / "synergy-cache", 2, 0.2)
            lab_path = guide
            lab = json.loads(lab_path.read_text())
            self.assertTrue(lab["complete"])
            self.assertTrue(lab["measuredSynergies"])
            self.assertLessEqual(len(lab["measuredSynergies"]), 24)
            for row in lab["measuredSynergies"]:
                # A buff is judged against the attack that would take its slot, a pair against its solo scores.
                self.assertEqual(row["baselineKind"], "slot-alternative-measured" if row["buffs"] else "solo-score-sum")
            self.assertTrue(any(row["effects"] for row in lab["moves"]))
            self.assertEqual(len(lab["moves"]), sum(m["kind"] != "buff" for m in game["moves"].values()))
            manifest = json.loads((SIM / "runpod/ranking-smoke.json").read_text())
            manifest.update(engineFingerprint=self.command("fingerprint").stdout.strip(),
                            secondsPerMatch=0.2, threads=2)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            self.command("ranking", "plan", manifest_path, lab_path, plan)
            planned = json.loads(plan.read_text())
            counts = planned["counts"]["strata"]
            self.assertTrue(counts)
            # 12 move groups per stratum, each fanned out to at most 5 natures (neutral + 4).
            self.assertLessEqual(max(counts.values()), 12 * 5)
            self.command("ranking", "run", plan, cache, output)
            first = json.loads(output.read_text())
            self.assertTrue(first["complete"])
            self.assertTrue(first["winners"])
            self.assertTrue(set(first["seedSets"]["screening"]).isdisjoint(first["seedSets"]["confirmation"]))
            before = {p.name: p.stat().st_mtime_ns for p in cache.glob("*.json")}
            self.assertTrue(before)
            manifest["threads"] = 1
            manifest_path.write_text(json.dumps(manifest))
            self.command("ranking", "plan", manifest_path, lab_path, plan)
            self.assertNotEqual(planned["planHash"], json.loads(plan.read_text())["planHash"])
            self.command("ranking", "resume", plan, cache, output)
            second = json.loads(output.read_text())
            self.assertEqual(first["winners"], second["winners"])
            self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in cache.glob("*.json")})
            _same_provenance(lab, second, game)
            self.assertEqual(len(export_attacks(lab)["moves"]), len(lab["moves"]))
            document = export_ranking(second, game)
            self.assertTrue(document["results"])
            validate_results(document, game)

    def test_old_funnel_requires_an_explicit_legacy_command(self):
        result = subprocess.run([str(BINARY), "funnel"], cwd=SIM, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("archived", result.stderr)
