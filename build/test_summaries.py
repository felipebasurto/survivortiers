"""The summary claim checker rejects what it should.  python3 -m unittest build/test_summaries.py

The base text is the worked example in build/prompts/summary.md (Kommo-o), so the prompt and the checker
cannot drift apart.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts_export  # noqa: E402
import summaries as S  # noqa: E402
import summary_facts as sf  # noqa: E402

FACTS = facts_export.load()
NAMES = S.all_build_names(FACTS)
PROMPT = (Path(__file__).resolve().parent / "prompts" / "summary.md").read_text(encoding="utf8")
EXAMPLE = json.loads(re.search(r"```json\n(.*?)\n```", PROMPT, re.S).group(1))


def errors(f: dict, entry: dict) -> list[str]:
    return S.validate(str(f["dex"]), entry, f, NAMES)


class Validator(unittest.TestCase):
    def setUp(self):
        self.f = FACTS[str(EXAMPLE["dex"])]
        self.entry = {"fp": sf.fingerprint(self.f), "es": EXAMPLE["es"], "en": EXAMPLE["en"]}

    def edit(self, es=None, en=None, **kw):
        return dict(self.entry, **({"es": es} if es else {}), **({"en": en} if en else {}), **kw)

    def test_prompt_example_passes(self):
        self.assertEqual(errors(self.f, self.entry), [])

    def test_shipped_summaries_pass(self):
        errs, stats = S.check(FACTS, S.load())
        self.assertEqual(errs, [])
        self.assertEqual(stats["species"] + stats["flagged"], 966)

    def test_unsupported_adjective_inside_a_mark(self):
        e = self.edit(es="[atk+|Rápido] " + self.entry["es"])
        self.assertTrue(any("«Rápido»" in x for x in errors(self.f, e)))

    def test_claim_key_must_hold(self):
        e = self.edit(es=self.entry["es"].replace("[atk+|", "[atk-|", 1), en=self.entry["en"].replace("[atk+|", "[atk-|", 1))
        self.assertTrue(any("atk-" in x for x in errors(self.f, e)))

    def test_claim_outside_a_mark(self):
        e = self.edit(es=self.entry["es"] + " Es rápido.")
        self.assertTrue(any("fuera de marca" in x for x in errors(self.f, e)))

    def test_move_name_must_match_the_build(self):
        other = next(n for n in sorted(NAMES["es"]) if n not in S.names_in(self.f, "es"))
        e = self.edit(es=self.entry["es"].replace("|Furia Dragón]", f"|{other}]", 1))
        self.assertTrue(any("build" in x for x in errors(self.f, e)))

    def test_move_id_must_match_the_build(self):
        e = self.edit(es=self.entry["es"].replace("m.start:dragon-rage|", "m.start:tackle|", 1),
                      en=self.entry["en"].replace("m.start:dragon-rage|", "m.start:tackle|", 1))
        self.assertTrue(any("m.start:tackle" in x for x in errors(self.f, e)))

    def test_tier_letter_must_be_backed(self):
        e = self.edit(es=self.entry["es"] + " No llega al S.")
        self.assertTrue(any("«S»" in x for x in errors(self.f, e)))

    def test_driver_must_be_a_top_driver(self):
        weak = min(S.DIRECTION, key=lambda k: abs(S._places(self.f, k)))
        e = self.edit(es=self.entry["es"].replace("[down:hitbox|", f"[up:{weak}|", 1),
                      en=self.entry["en"].replace("[down:hitbox|", f"[up:{weak}|", 1))
        self.assertTrue(any(f"up:{weak}" in x for x in errors(self.f, e)))

    def test_languages_must_agree(self):
        e = self.edit(en=self.entry["en"].replace("[td+|shrugs off enemy types]", "shrugs it off", 1))
        self.assertTrue(any("no dicen lo mismo" in x for x in errors(self.f, e)))

    def test_must_cover_build_and_rank(self):
        e = self.edit(es=self.entry["es"].replace("; lleva [i.best:luckyegg|Huevo Suerte]", ""),
                      en=self.entry["en"].replace("; carry [i.best:luckyegg|Lucky Egg]", ""))
        self.assertTrue(any("i.best" in x for x in errors(self.f, e)))

    def test_stale_fingerprint(self):
        self.assertTrue(any("huella" in x for x in errors(self.f, self.edit(fp="000000000000"))))

    def test_numbers_are_not_allowed(self):
        self.assertTrue(errors(self.f, self.edit(es=self.entry["es"] + " En 90 s.")))

    def test_base_record_as_catalog_sees_it(self):
        base = sf.base_records()[str(EXAMPLE["dex"])]
        self.assertEqual(base, sf.base_of(self.f))
        e = dict(self.entry, bfp=sf.fingerprint(base))
        self.assertEqual(errors(base, e), [])
        self.assertTrue(any("huella" in x for x in errors(base, dict(e, bfp="000000000000"))))
        self.assertTrue(any("«Rápido»" in x for x in errors(base, dict(e, es="Rápido. " + e["es"]))))


if __name__ == "__main__":
    unittest.main()
