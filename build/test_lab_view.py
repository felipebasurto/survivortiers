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

    def test_moves_page_labels_measurements_separately(self):
        from build.render import laboratory_table
        from build.i18n import Lang
        move = {"id": "ember", "name": "Ascuas", "en": {"name": "Ember"},
                "laboratory": fixture()["moves"][0]}
        es = laboratory_table(Lang("es"), [move])
        en = laboratory_table(Lang("en"), [move])
        self.assertIn("Ascuas", es)
        self.assertIn("Clasificación histórica", es)
        self.assertIn("Initial DPS", en)
        self.assertIn("Maximum-level DPS", en)
        self.assertEqual(laboratory_table(Lang("es"), []), "")
