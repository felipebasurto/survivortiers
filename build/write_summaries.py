"""Rewrite ficha summaries whose facts changed.

The wording is filled from the claims the checker already allows, so a sentence can
only say what the current build and the current rank drivers support. Species whose
fingerprint still matches are left as they are.

    python3 build/write_summaries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summaries  # noqa: E402
import summary_facts as sf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "facts.parquet"

TRAIT_ORDER = ("atk+", "spd+", "hp+", "td+", "hb+", "atk-", "spd-", "hp-", "td-", "hb0", "avg")


def load_records() -> dict[str, dict]:
    import pyarrow.parquet as pq

    table = pq.read_table(PARQUET, columns=["dex", "record"])
    out = {}
    for dex, rec in zip(table.column("dex").to_pylist(), table.column("record").to_pylist()):
        out[str(dex)] = json.loads(rec)
    return out


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _join(parts: list[str], lang: str) -> str:
    if len(parts) == 1:
        return parts[0]
    conj = " y " if lang == "es" else " and "
    if len(parts) == 2:
        return parts[0] + conj + parts[1]
    return ", ".join(parts[:-1]) + conj + parts[-1]


def _traits(claims: dict[str, dict], lang: str) -> str:
    keys = [k for k in TRAIT_ORDER if k in claims][:3]
    if not keys:
        keys = ["avg"] if "avg" in claims else []
    bits = []
    for i, k in enumerate(keys):
        word = claims[k][lang]
        if i == 0:
            word = _cap(word)
        bits.append(f"[{k}|{word}]")
    return _join(bits, lang) + "."


def _build(f: dict, claims: dict[str, dict], lang: str) -> str:
    b = f["build"]
    start = b["start"]
    start_m = f"[m.start:{start['id']}|{start[lang]}]"
    group = [m for m in b["group"] if m["id"] != start["id"]]
    item = b["item"]
    item_m = f"[i.best:{item['id']}|{item[lang]}]"
    if lang == "es":
        if group:
            bonded = _join([f"[m.group:{m['id']}|{m['es']}]" for m in group], "es")
            return f"Empieza con {start_m} y vincula {bonded}; lleva {item_m}."
        return f"Empieza con {start_m}; lleva {item_m}."
    if group:
        bonded = _join([f"[m.group:{m['id']}|{m['en']}]" for m in group], "en")
        return f"Start with {start_m} and bond {bonded}; carry {item_m}."
    return f"Start with {start_m}; carry {item_m}."


def _why(claims: dict[str, dict], lang: str) -> str:
    ups = [k for k in claims if k.startswith("up:") and k.count(":") == 1]
    downs = [k for k in claims if k.startswith("down:") and k.count(":") == 1]
    if ups:
        k = ups[0]
        return f"Lo que más lo sube es [{k}|{claims[k][lang]}]." if lang == "es" else f"What lifts it most is [{k}|{claims[k][lang]}]."
    if downs:
        k = downs[0]
        return f"Lo que más lo frena es [{k}|{claims[k][lang]}]." if lang == "es" else f"What holds it back most is [{k}|{claims[k][lang]}]."
    if "nodown" in claims:
        return "[nodown|Nada lo frena]." if lang == "es" else "[nodown|Nothing holds it back]."
    return "[calm|Ningún factor mueve el puesto]." if lang == "es" else "[calm|No single factor moves the rank]."


def render(f: dict) -> tuple[str, str]:
    claims = {c["key"]: c for c in summaries.claims(f)}
    es = " ".join((_traits(claims, "es"), _build(f, claims, "es"), _why(claims, "es")))
    en = " ".join((_traits(claims, "en"), _build(f, claims, "en"), _why(claims, "en")))
    # Stay inside the length cap by dropping the third trait, then the second.
    for _ in range(3):
        if len(summaries.plain(es)) <= summaries.MAX_LEN and len(summaries.plain(en)) <= summaries.MAX_LEN:
            break
        # Rebuild traits with one fewer by blanking the last trait key we used.
        used = [k for k in TRAIT_ORDER if f"[{k}|" in es]
        if len(used) <= 1:
            break
        claims.pop(used[-1], None)
        es = " ".join((_traits(claims, "es"), _build(f, claims, "es"), _why(claims, "es")))
        en = " ".join((_traits(claims, "en"), _build(f, claims, "en"), _why(claims, "en")))
    return es, en


def main() -> None:
    records = load_records()
    blob = summaries.load()
    species = blob["species"]
    names = summaries.all_build_names(records)
    changed = 0
    for dex, f in records.items():
        base = sf.base_of(f)
        fp, bfp = sf.fingerprint(f), sf.fingerprint(base)
        entry = species.get(dex)
        if entry and entry.get("fp") == fp and entry.get("bfp") == bfp:
            errs = summaries.validate(dex, entry, f, names)
            if not errs:
                continue
        es, en = render(f)
        species[dex] = {"fp": fp, "bfp": bfp, "es": es, "en": en}
        changed += 1
    errs, stats = summaries.check(records, blob)
    if errs:
        print("\n".join(errs[:30]))
        raise SystemExit(f"{len(errs)} summary errors after rewrite")
    sf.DATA.joinpath("summaries.json").write_text(
        json.dumps(blob, ensure_ascii=False, indent=1) + "\n", encoding="utf8"
    )
    print(f"rewrote {changed} summaries; {stats}")


if __name__ == "__main__":
    main()
