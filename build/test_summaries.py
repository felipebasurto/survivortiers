"""The summary validator rejects what it should.  python3 -m unittest build/test_summaries.py"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summaries as S  # noqa: E402

FACTS = json.loads(S.summary_facts.OUT.read_text(encoding="utf8"))
NAMES = S.all_build_names(FACTS)


def species(pred):
    return next(f for f in FACTS["species"].values() if pred(f))


def errors(f: dict, entry: dict) -> list[str]:
    return S.validate(str(f["dex"]), entry, f, NAMES)


class Validator(unittest.TestCase):
    def setUp(self):
        self.slow = species(lambda f: f["stats"]["spd"]["pct"] <= S.LOW and f["hitbox"]["r"] > f["hitbox"]["median"])
        self.entry = S.compose(self.slow)

    def test_composed_text_passes(self):
        for f in list(FACTS["species"].values())[::50]:
            self.assertEqual(errors(f, S.compose(f)), [], f["name"])

    def test_unsupported_adjective_inside_a_mark(self):
        e = dict(self.entry, es="[spd-|Rápido] " + self.entry["es"])
        self.assertTrue(any("«Rápido»" in x for x in errors(self.slow, e)))

    def test_claim_key_must_hold(self):
        e = dict(self.entry, es=self.entry["es"].replace("[spd-|", "[spd+|", 1), en=self.entry["en"].replace("[spd-|", "[spd+|", 1))
        self.assertTrue(any("spd+" in x for x in errors(self.slow, e)))

    def test_claim_outside_a_mark(self):
        e = dict(self.entry, es=self.entry["es"] + " Tiene hitbox pequeño.")
        self.assertTrue(any("fuera de marca" in x for x in errors(self.slow, e)))

    def test_move_name_must_match_the_build(self):
        start = self.slow["build"]["start"]
        other = next(n for n in sorted(NAMES["es"]) if n not in S.names_in(self.slow, "es"))
        e = dict(self.entry, es=self.entry["es"].replace(f"|{start['es']}]", f"|{other}]", 1))
        self.assertTrue(any("build" in x for x in errors(self.slow, e)))

    def test_move_id_must_match_the_build(self):
        start = self.slow["build"]["start"]["id"]
        e = dict(self.entry, es=self.entry["es"].replace(f"m.start:{start}|", "m.start:tackle-x|", 1))
        self.assertTrue(errors(self.slow, e))

    def test_tier_letter_must_be_backed(self):
        e = dict(self.entry, es=self.entry["es"] + " No llega al S.")
        self.assertTrue(any("«S»" in x for x in errors(self.slow, e)))

    def test_driver_must_be_a_top_driver(self):
        f = self.slow
        weak = min(S.DIRECTION, key=lambda k: abs(S._places(f, k)))
        e = dict(self.entry, es=self.entry["es"] + f" [up:{weak}|Algo].", en=self.entry["en"] + f" [up:{weak}|Something].")
        self.assertTrue(any(f"up:{weak}" in x for x in errors(f, e)))

    def test_languages_must_agree(self):
        e = dict(self.entry, en=self.entry["en"].replace("[hb-|", "[x|", 1))
        self.assertTrue(any("no dicen lo mismo" in x for x in errors(self.slow, e)))

    def test_stale_fingerprint(self):
        e = dict(self.entry, fp="000000000000")
        self.assertTrue(any("huella" in x for x in errors(self.slow, e)))

    def test_numbers_are_not_allowed(self):
        e = dict(self.entry, es=self.entry["es"] + " Dura 90 s.")
        self.assertTrue(errors(self.slow, e))


if __name__ == "__main__":
    unittest.main()
