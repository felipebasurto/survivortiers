import copy
import unittest

from build.lab_view import laboratory_rows


def fixture():
    from build.test_laboratory_export import lab_doc
    data = lab_doc()
    data.update(kind="attack-lab-export", gameCommit="game", engineFingerprint="engine")
    return data


class LaboratoryViewTests(unittest.TestCase):
    def test_observed_dps_is_preserved(self):
        self.assertEqual(laboratory_rows(fixture(), "game")["water-gun"]["lateScore"], 3.4)

    def test_stale_or_incomplete_artifacts_are_rejected(self):
        for key, value in (("gameCommit", "old"), ("complete", False), ("engineFingerprint", "")):
            data = fixture()
            data[key] = value
            with self.assertRaises(ValueError):
                laboratory_rows(data, "game")

    def test_invalid_measurements_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, True, None):
            data = fixture()
            data["moves"][0]["score"] = value
            with self.assertRaises(ValueError):
                laboratory_rows(data, "game")

    def test_duplicate_ids_are_rejected(self):
        data = fixture()
        data["moves"].append(copy.deepcopy(data["moves"][0]))
        with self.assertRaises(ValueError):
            laboratory_rows(data, "game")

    def test_partial_and_smoke_runs_cannot_be_displayed_as_full(self):
        for change in ({"scope": "filtered-moves", "partialScope": True}, {"secondsPerScenario": 15}):
            data = fixture()
            data.update(change)
            with self.assertRaises(ValueError):
                laboratory_rows(data, "game")

    def test_effects_must_be_known_and_unique(self):
        for effects in (["fire"], ["burn", "burn"], "burn"):
            data = fixture()
            data["moves"][0]["effects"] = effects
            with self.assertRaises(ValueError):
                laboratory_rows(data, "game")

    def test_moves_page_keeps_boss_group_and_approach_damage_apart(self):
        from build.render import laboratory_table
        from build.i18n import Lang
        lab = fixture()["moves"][0]
        lab["effects"] = ["burn", "slow"]
        # Distinct values per situation, so a merged column could not pass.
        values = {"boss-1": 10.0, "line-3": 20.0, "line-12": 40.0, "surround-3": 60.0,
                  "surround-12": 80.0, "approach-3": 100.0, "approach-12": 300.0}
        for row in lab["scenarios"]:
            base = values[row["id"].rsplit("-", 1)[0]]
            row["damagePerSecond"] = base if row["phase"] == "initial" else base * 2
        move = {"id": "ember", "name": "Ascuas", "en": {"name": "Ember"}, "kind": "projectile",
                "type": "fire", "mech": {"homing": 0, "pierce": 0, "count": 1}, "laboratory": lab}
        es = laboratory_table(Lang("es"), [move])
        en = laboratory_table(Lang("en"), [move])
        self.assertIn("Ascuas", es)
        self.assertIn("Contra jefe", es)
        self.assertIn("Contra grupos", es)
        self.assertIn("Con enemigos entrando", es)
        self.assertIn("Against a boss", en)
        self.assertIn("With enemies approaching", en)
        self.assertIn("Quemadura", es)
        self.assertIn("Burn", en)
        # boss 10 → 20, groups (20+40+60+80)/4 = 50 → 100, approaching (100+300)/2 = 200 → 400.
        for cell in ("10,0", "20,0", "50,0", "100,0", "200,0", "400,0"):
            self.assertIn(cell, es)
        self.assertIn('class="lab-row" data-q="ascuas ember', es)
        self.assertNotIn("Clasificación histórica", es)
        self.assertEqual(laboratory_table(Lang("es"), []), "")
