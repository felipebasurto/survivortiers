"""Ficha summaries pipeline: facts -> writers -> claim check (with retries) -> data/summaries.json.

    python3 build/facts_export.py                   # 1. facts: data/facts.parquet
    python3 build/summary_pipeline.py plan          # 2. batches + one writer prompt per batch (.cache/summaries/)
       ... a writer per prompt (Grok subagent) writes .cache/summaries/out/<round>-<batch>.jsonl
    python3 build/summary_pipeline.py validate      # 3. checks every output; writes retry prompts for failures
       ... writers for the retry prompts, then validate again (2 retries at most, then the species is flagged)
    python3 build/summary_pipeline.py assemble      # 4. data/summaries.json (+ the cache of untouched species)
    python3 build/summary_pipeline.py check         # data/summaries.json against data/facts.parquet

The cache is the `fp` stored with each text: the hash of that species' facts row. `plan` only sends species whose
row changed, that have no text or whose text no longer passes; `plan --all` sends all 966.
Writer output, one JSON object per line: {"dex": 784, "es": "...", "en": "..."}.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts_export  # noqa: E402
import summaries  # noqa: E402
import summary_facts as sf  # noqa: E402

ROOT = sf.ROOT
WORK = ROOT / ".cache" / "summaries"
OUTDIR = WORK / "out"
STATE = WORK / "state.json"
PROMPT = ROOT / "build" / "prompts" / "summary.md"
MAX_ROUNDS = 3  # first write + 2 retries
RETRY_BATCH = 25


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def render(name: str, ids: list[int], out: Path, notes: str) -> Path:
    text = (PROMPT.read_text(encoding="utf8")
            .replace("{{PARQUET}}", rel(facts_export.OUT)).replace("{{ROOT}}", str(ROOT))
            .replace("{{IDS}}", ", ".join(map(str, ids))).replace("{{OUT}}", rel(out))
            .replace("{{RETRY_NOTES}}", notes))
    path = WORK / f"{name}.prompt.md"
    path.write_text(text, encoding="utf8")
    return path


def chunks(ids: list[int], size: int) -> list[list[int]]:
    n = max(1, -(-len(ids) // size))
    k = -(-len(ids) // n)
    return [ids[i:i + k] for i in range(0, len(ids), k)]


def outputs(state: dict) -> dict[int, dict[str, dict]]:
    """round -> dex -> last line written for it in that round."""
    by_round: dict[int, dict[str, dict]] = {}
    for b in state["batches"]:
        path = ROOT / b["out"]
        lines = path.read_text(encoding="utf8").splitlines() if path.exists() else []
        got = by_round.setdefault(b["round"], {})
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                d = str(int(o["dex"]))
            except (ValueError, KeyError, TypeError):
                continue
            if int(d) in b["ids"]:
                got[d] = {"es": o.get("es", ""), "en": o.get("en", "")}
    return by_round


def errors_for(d: str, text: dict, f: dict, names: dict) -> list[str]:
    entry = {"fp": sf.fingerprint(f), **text}
    if not isinstance(entry["es"], str) or not isinstance(entry["en"], str):
        return ["es y en deben ser textos"]
    errs = summaries.validate(d, entry, f, names)
    return [e.split(": ", 1)[1] if e.startswith(d + " ") else e for e in errs]


def plan(args) -> int:
    facts = facts_export.load()
    cache = summaries.load()["species"]
    names = summaries.all_build_names(facts)
    need = [int(d) for d, f in facts.items()
            if args.all or d not in cache or cache[d].get("fp") != sf.fingerprint(f)
            or errors_for(d, cache[d], f, names)]
    shutil.rmtree(WORK, ignore_errors=True)
    OUTDIR.mkdir(parents=True)
    batches = []
    for i, ids in enumerate(chunks(sorted(need), args.batch), start=1):
        name = f"r1-b{i:02d}"
        out = OUTDIR / f"{name}.jsonl"
        batches.append({"name": name, "round": 1, "ids": ids, "out": rel(out),
                        "prompt": rel(render(name, ids, out, ""))})
    STATE.write_text(json.dumps({"round": 1, "batches": batches}, indent=1), encoding="utf8")
    print(f"plan: {len(need)} de {len(facts)} especies por escribir, {len(batches)} lotes "
          f"({len(facts) - len(need)} siguen en caché)")
    for b in batches:
        print(f"  {b['prompt']}  ({len(b['ids'])} especies) -> {b['out']}")
    return 0


def judge(state: dict, facts: dict) -> tuple[dict, dict, dict]:
    """ok: dex -> text that passes; failed: dex -> (round, errors, text); attempts: dex -> rounds it was sent."""
    names = summaries.all_build_names(facts)
    by_round = outputs(state)
    attempts: dict[str, int] = {}
    for b in state["batches"]:
        for d in b["ids"]:
            attempts[str(d)] = attempts.get(str(d), 0) + 1
    ok, failed = {}, {}
    for r in sorted(by_round):
        for b in (b for b in state["batches"] if b["round"] == r):
            for d in map(str, b["ids"]):
                if d in ok:
                    continue
                text = by_round[r].get(d)
                errs = ["no hay línea para este Pokémon en la salida"] if text is None else errors_for(d, text, facts[d], names)
                if errs:
                    failed[d] = (r, errs, text)
                else:
                    ok[d] = text
                    failed.pop(d, None)
    return ok, failed, attempts


def validate(args) -> int:
    state = json.loads(STATE.read_text(encoding="utf8"))
    facts = facts_export.load()
    ok, failed, attempts = judge(state, facts)
    r = state["round"]
    print(f"ronda {r}: {len(ok)} pasan, {len(failed)} fallan")
    for d, (_, errs, _) in sorted(failed.items(), key=lambda kv: int(kv[0]))[:30]:
        print(f"  {d} {facts[d]['name']}: {errs[0]}" + (f" (+{len(errs) - 1})" if len(errs) > 1 else ""))
    retry = sorted(int(d) for d in failed if attempts[d] < MAX_ROUNDS)
    flagged = sorted(int(d) for d in failed if attempts[d] >= MAX_ROUNDS)
    if flagged:
        print(f"  {len(flagged)} marcados tras {MAX_ROUNDS} intentos: {flagged}")
    if not retry:
        print("nada que reintentar: python3 build/summary_pipeline.py assemble")
        return 0
    state["round"] = r + 1
    for i, ids in enumerate(chunks(retry, RETRY_BATCH), start=1):
        name = f"r{r + 1}-b{i:02d}"
        out = OUTDIR / f"{name}.jsonl"
        notes = ["## Retry: these species failed the claim check", "",
                 "Rewrite each one from its facts. Fix exactly these errors; everything else in the rules still holds.", ""]
        for d in ids:
            _, errs, text = failed[str(d)]
            notes.append(f"- dex {d} ({facts[str(d)]['nameEn']}):")
            notes += [f"  - error: {e}" for e in errs]
            if text:
                notes.append(f"  - your previous es: {text.get('es', '')}")
                notes.append(f"  - your previous en: {text.get('en', '')}")
        state["batches"].append({"name": name, "round": r + 1, "ids": ids, "out": rel(out),
                                 "prompt": rel(render(name, ids, out, "\n".join(notes) + "\n"))})
    STATE.write_text(json.dumps(state, indent=1), encoding="utf8")
    print(f"ronda {r + 1}: {len(retry)} especies a reintentar")
    for b in state["batches"]:
        if b["round"] == r + 1:
            print(f"  {b['prompt']}  ({len(b['ids'])} especies) -> {b['out']}")
    return 0


def assemble(args) -> int:
    state = json.loads(STATE.read_text(encoding="utf8"))
    facts = facts_export.load()
    ok, failed, attempts = judge(state, facts)
    old = summaries.load()
    names = summaries.all_build_names(facts)
    species, flagged = {}, {}
    counts = {"written": 0, "kept": 0, "flagged": 0, "retried": sum(1 for d in ok if attempts[d] > 1)}
    for d, f in facts.items():
        fp, bfp = sf.fingerprint(f), sf.fingerprint(sf.base_of(f))
        if d in ok:
            species[d] = {"fp": fp, "bfp": bfp, "es": ok[d]["es"], "en": ok[d]["en"]}
            counts["written"] += 1
        elif d not in failed and d in old["species"] and not errors_for(d, old["species"][d], f, names):
            species[d] = {**old["species"][d], "bfp": bfp}
            counts["kept"] += 1
        else:
            flagged[d] = failed[d][1] if d in failed else ["sin texto válido"]
            counts["flagged"] += 1
    doc = {"note": "Escrito por build/summary_pipeline.py (escritores Grok con build/prompts/summary.md a partir de "
                   "data/facts.parquet). Las marcas [clave|texto] dicen qué dato respalda cada afirmación; "
                   "fp es la huella de la fila de datos y hace de caché.",
           "thresholds": summaries.THRESHOLDS, "species": species, "flagged": flagged}
    summaries.PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"assemble: {counts['written']} escritos ({counts['retried']} tras reintento), {counts['kept']} de caché, "
          f"{counts['flagged']} marcados -> {rel(summaries.PATH)}")
    return check(args)


def check(args) -> int:
    facts = facts_export.load()
    doc = summaries.load()
    errs, stats = summaries.check(facts, doc)
    for e in errs[:40]:
        print("  " + e, file=sys.stderr)
    print(f"validación: {stats['species']} Pokémon, {stats['texts']} textos, {stats['claims']} afirmaciones, "
          f"{stats['flagged']} marcados, {len(errs)} errores")
    return 1 if errs else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--all", action="store_true", help="rewrite every species, not only the changed ones")
    p.add_argument("--batch", type=int, default=40)
    sub.add_parser("validate")
    sub.add_parser("assemble")
    sub.add_parser("check")
    args = ap.parse_args()
    return {"plan": plan, "validate": validate, "assemble": assemble, "check": check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
