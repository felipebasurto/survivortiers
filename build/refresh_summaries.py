"""Keep data/summaries.json aligned with data/facts.parquet.

Species whose claims still hold keep their prose; only the fingerprints move.
Species whose marks no longer match the build or the rank drivers are rewritten
from the claims the checker allows (build/summaries.py). Same keys in Spanish
and English, 2-3 sentences, no digits.

    python3 build/refresh_summaries.py
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts_export  # noqa: E402
import summaries as S  # noqa: E402
import summary_facts as sf  # noqa: E402

POS = ("atk+", "spd+", "hp+", "hb+", "td+")
NEG = ("atk-", "spd-", "hp-", "td-")
BUFFS = {"buff"}
ATTACK_BUFFS = ("nasty-plot", "swords-dance", "dragon-dance")


def _i_sound(word: str) -> bool:
    w = "".join(c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c))
    if w.startswith("i"):
        return True
    return w.startswith("hi") and w[2:3] not in ("a", "e", "i", "o", "u")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _mark(key: str, text: str) -> str:
    return f"[{key}|{text}]"


def _vis(mark: str) -> str:
    return mark.split("|", 1)[1][:-1]


def _join(marks: list[str], lang: str) -> str:
    if len(marks) <= 1:
        return marks[0] if marks else ""
    if lang == "en":
        conj = " and "
    else:
        conj = " e " if _i_sound(_vis(marks[-1])) else " y "
    if len(marks) == 2:
        return marks[0] + conj + marks[1]
    return ", ".join(marks[:-1]) + conj + marks[-1]


def _by_key(claims: list[dict]) -> dict[str, dict]:
    return {c["key"]: c for c in claims}


def _traits(claims: list[dict], lang: str, limit: int) -> str:
    got = _by_key(claims)
    pos = [k for k in POS if k in got]
    neg = [k for k in NEG if k in got]
    if neg:
        pos = pos[: max(0, limit - 1)]
        neg = neg[: max(1, limit - len(pos))]
    else:
        pos = pos[:limit]
    if not pos and not neg:
        for k in ("avg", "hb0"):
            if k in got:
                return _mark(k, _cap(got[k][lang])) + "."
        return ""

    def one(k: str, first: bool) -> str:
        text = got[k][lang]
        return _mark(k, _cap(text) if first else text)

    if pos and neg:
        left = _join([one(k, i == 0) for i, k in enumerate(pos)], lang)
        right = _join([one(k, False) for k in neg], lang)
        bridge = ", pero " if lang == "es" else ", but "
        if lang == "en" and any(k.startswith("hb") for k in neg):
            right = "a " + right
        return left + bridge + right + "."
    if pos:
        return _join([one(k, i == 0) for i, k in enumerate(pos)], lang) + "."
    lead = "Tiene " if lang == "es" else "Has "
    if lang == "en" and any(k.startswith("hb") for k in neg):
        lead = "Has a "
    return lead + _join([one(k, False) for k in neg], lang) + "."


def _build(f: dict, claims: list[dict], lang: str, groups: int, alt: bool) -> str:
    got = _by_key(claims)
    start = got["m.start:" + f["build"]["start"]["id"]]
    item = got["i.best:" + f["build"]["item"]["id"]]
    kind = {m["id"]: m["kind"] for m in f["build"]["group"]}
    attacks, boosts = [], []
    for c in claims:
        if not c["key"].startswith("m.group:"):
            continue
        (boosts if kind.get(c["key"].split(":", 1)[1]) in BUFFS else attacks).append(c)
    chosen = (attacks or boosts)[:groups]
    # The attack buff is part of the bonded group. Harden can stay off the sentence.
    buff = next((c for c in boosts if c["key"].split(":", 1)[1] in ATTACK_BUFFS), None)
    if groups and buff is not None and buff not in chosen:
        chosen.append(buff)
    spare = next((c for c in claims if c["key"].startswith("m.alt:")), None) if alt else None

    def M(c: dict) -> str:
        return _mark(c["key"], c[lang])

    if lang == "es":
        text = "Empieza con " + M(start)
        if chosen:
            head = M(chosen[0])
            if spare:
                head += " (o " + M(spare) + ")"
            rest = [_mark(c["key"], c[lang]) for c in chosen[1:]]
            text += " y vincula " + _join([head, *rest], "es")
        text += "; lleva " + M(item) + "."
        return text
    text = "Start with " + M(start)
    if chosen:
        head = M(chosen[0])
        if spare:
            head += " (or " + M(spare) + ")"
        rest = [_mark(c["key"], c[lang]) for c in chosen[1:]]
        text += ", bond " + _join([head, *rest], "en")
    text += "; carry " + M(item) + "."
    return text


def _reason(claims: list[dict], lang: str) -> str:
    ups = [c for c in claims if c["key"].startswith("up:") and c["key"].count(":") == 1]
    downs = [c for c in claims if c["key"].startswith("down:") and c["key"].count(":") == 1]
    down_t = [c for c in claims if c["key"].startswith("down:") and c["key"].count(":") == 2]
    up_t = [c for c in claims if c["key"].startswith("up:") and c["key"].count(":") == 2]
    nodown = next((c for c in claims if c["key"] == "nodown"), None)
    calm = next((c for c in claims if c["key"] == "calm"), None)

    def M(c: dict, first: bool = False) -> str:
        return _mark(c["key"], _cap(c[lang]) if first else c[lang])

    if down_t:
        return M(down_t[0], True) + "."
    if up_t and not downs:
        return M(up_t[0], True) + "."
    if ups and downs:
        if lang == "es":
            return f"Lo que más lo sube es {M(ups[0])}, y lo que más lo baja es {M(downs[0])}."
        return f"What lifts it most is {M(ups[0])}, and what holds it back most is {M(downs[0])}."
    if ups and nodown:
        if lang == "es":
            return f"Lo que más lo sube es {M(ups[0])}, y {M(nodown)} de verdad."
        return f"What lifts it most is {M(ups[0])}, and {M(nodown)} much."
    if ups:
        if lang == "es":
            return f"Lo que más lo sube es {M(ups[0])}."
        return f"What lifts it most is {M(ups[0])}."
    if downs:
        if lang == "es":
            return f"Lo que más lo baja es {M(downs[0])}."
        return f"What holds it back most is {M(downs[0])}."
    if calm:
        if lang == "es":
            return M(calm, True) + " pesa en el puesto."
        return M(calm, True) + " moves it much."
    if nodown:
        return M(nodown, True) + "."
    raise SystemExit("sin razón de puesto en las claims")


def compose(f: dict) -> tuple[str, str]:
    """Two or three sentences whose marks are exactly the claims that hold."""
    claims = S.claims(f)
    for groups, alt, ntrait in ((2, True, 3), (2, False, 3), (1, False, 3), (1, False, 2), (0, False, 2), (0, False, 1)):
        parts = []
        for lang in ("es", "en"):
            bits = [b for b in (_traits(claims, lang, ntrait), _build(f, claims, lang, groups, alt), _reason(claims, lang)) if b]
            parts.append(" ".join(bits))
        if all(len(S.plain(p)) <= S.MAX_LEN for p in parts):
            return parts[0], parts[1]
    raise SystemExit(f"{f['dex']}: el resumen no cabe en {S.MAX_LEN} caracteres")


def _real_errors(errs: list[str]) -> list[str]:
    return [e for e in errs if "huella" not in e]


def _live(base_rec: dict, full: dict) -> dict:
    """Base record catalog checks, plus the stored rank drivers so the reason sentence has a source.
    Counterfactuals are not recomputed here; a driver that no longer holds is dropped by the checker."""
    rec = dict(base_rec)
    if "drivers" in full:
        rec["drivers"] = full["drivers"]
    if "ungated" in full:
        rec["ungated"] = full["ungated"]
    return rec


def refresh(write: bool = True) -> dict[str, int]:
    facts = facts_export.load()
    # catalog.py checks the live base record (ranking, build, capped hitbox), not a stale parquet copy.
    base = sf.base_records()
    doc = S.load()
    names = S.all_build_names(facts)
    kept = rewritten = 0
    species = {}
    for d, f in facts.items():
        live = _live(base[d], f)
        old = doc["species"].get(d)
        fp, bfp = sf.fingerprint(live), sf.fingerprint(base[d])
        if old is None:
            text = dict(zip(("es", "en"), compose(live)))
            rewritten += 1
        else:
            trial = {**old, "fp": fp, "bfp": bfp}
            if _real_errors(S.validate(d, trial, live, names)):
                text = dict(zip(("es", "en"), compose(live)))
                rewritten += 1
            else:
                text = {"es": old["es"], "en": old["en"]}
                kept += 1
        entry = {"fp": fp, "bfp": bfp, **text}
        errs = S.validate(d, entry, live, names)
        if errs:
            raise SystemExit(errs[0] + (f" (+{len(errs) - 1})" if len(errs) > 1 else ""))
        species[d] = entry
    base_names = S.all_build_names(base)
    for d, entry in species.items():
        errs = S.validate(d, entry, base[d], base_names)
        if errs:
            raise SystemExit("base " + errs[0])
    doc["species"] = species
    doc["flagged"] = {}
    if write:
        S.PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    return {"kept": kept, "rewritten": rewritten, "species": len(species)}


def main() -> int:
    counts = refresh(write="--check" not in sys.argv)
    print(f"resúmenes: {counts['kept']} conservados, {counts['rewritten']} reescritos, {counts['species']} en total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
