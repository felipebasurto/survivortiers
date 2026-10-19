"""Stage 1 of the summaries: every species' facts record, with the rank drivers, in one parquet file.

    python3 build/facts_export.py            # writes data/facts.parquet
    python3 build/facts_export.py --check    # fails if data/facts.parquet is not what the data gives today

Needs numpy and pyarrow (the hosting build does not; catalog.py only uses the stdlib part, summary_facts.py).
Deterministic: same inputs, same bytes. One row per species, sorted by dex. Flat columns for a quick look
(percentiles, hitbox, build names, drivers), `claims` (JSON: every claim key that holds for that species with
what it means and plain wording, which is all a writer needs), `record` (JSON: the full facts record the
validator uses) and `fp` / `bfp` (hash of the full record / of the record without drivers).

Drivers. The published order is the solo best-move sim score. The sheet and the v4 table stay in the
CSV and do not move a place. A stat bench that does not reproduce this ranking contributes 0 places.
  hitbox, speed, hp, attack  re-simulated with that stat at the median (simulator/counterfactual_bench.py,
                             results/fixed_group/counterfactuals_g2p2.csv, same seeds and flags as the rank).
                             hitbox also sets the size pillar to the median radius.
                             The bench resimulates the solo starter and the best move. The opening
                             measure is the Repertorio expectation, so the same score-delta is
                             applied to that expectation (the bench did not resimulate every
                             second attack). startS/bestS stay the solo gaps, in seconds.
  start_move                 the Repertorio opening score replaced by the median score over every
                             solo start the species can learn (starter_sweep.csv). startS is the
                             opening minus the solo median, in seconds.
  best_move                  the solo best score replaced by its second best start in the solo sweep
                             (simulator/results/fixed_group/solo_sweep.csv), ordered the same way as
                             make_definitive.winner_by_dex. bestS is the seconds that move adds.
                             (Against the median of its own moves it would lift every species.)
  stats, moves, typedef      that sheet pillar at 0.5.
  late                       both late-game ranks at the middle (483.5).
  gate                       published rank minus the ungated rank, for the species a tier gate held back.
Positive `places` means the factor lifts the species (without it, it would sit lower). Sim figures are estimates.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_definitive as md  # noqa: E402
import owner_rules  # noqa: E402
import summaries  # noqa: E402
import summary_facts as sf  # noqa: E402

OUT = sf.DATA / "facts.parquet"
CF_CSV = sf.SIM / "counterfactuals_g2p2.csv"
SWEEP_CSV = sf.SIM / "g2p2" / "starter_sweep.csv"
SOLO_SWEEP = sf.SIM / "solo_sweep.csv"
SOLO_CF = sf.SIM / "counterfactuals_solo.csv"
N = sf.N
PILLAR_W = {"stats": 45, "moves": 25, "typedef": 15, "size": 15}
SIM_STATS = {"r": "hitbox", "spd": "speed", "hp": "hp", "atk": "attack"}


def rank_among(value: float, others: np.ndarray) -> int:
    """1 + how many of the other species score higher."""
    return 1 + int((others > value).sum())


class Model:
    """Published order: the solo best-move sim score. The sheet and the v4 table do not move it."""

    def __init__(self, rows: list[dict], start_s: np.ndarray, best_s: np.ndarray):
        self.start_s, self.best_s = start_s, best_s
        self.point = best_s.copy()
        self.here = np.array([rank_among(float(best_s[i]), best_s[np.arange(N) != i]) for i in range(N)])

    def counterfactual(self, i: int, start_s=None, best_s=None, pillars: dict | None = None, late=False) -> int:
        """Rank of species i. Only a different best-move score moves it."""
        del start_s, pillars, late
        if best_s is None:
            return int(self.here[i])
        others = self.best_s[np.arange(N) != i]
        return rank_among(float(best_s), others)


def ungated_ranks(rows: list[dict]) -> dict[int, int]:
    """Position of each species before the tier gates, as make_definitive.main orders it."""
    starts = {int(r["dex"]): r for r in md.load_csv(sf.SIM / "g2p2" / "rank_200.csv")}
    sweep = md.load_csv(SWEEP_CSV)
    winners = md.winner_by_dex(md.load_csv(SOLO_SWEEP))
    sweep_moves = {(int(r["dex"]), r["start"]): r for r in sweep}
    arrays = md.sim_arrays(rows, starts, winners, sweep_moves, False, share_interval=False)
    start_s, slo, shi, best_s, blo, bhi, same = arrays[:7]
    opening = md.repertoire_opening(SWEEP_CSV)
    md.apply_repertoire(rows, start_s, slo, shi, opening)
    sheet = np.array([int(r["rank_sheet"]) for r in rows], dtype=float)
    v4m = np.array([int(r["rank_v4_max"]) for r in rows], dtype=float)
    v4f = np.array([int(r["rank_v4_fresh"]) for r in rows], dtype=float)
    _, _, point, fr = md.draw(start_s, slo, shi, best_s, blo, bhi, same, sheet, v4m, v4f)
    med = np.median(fr, axis=0)
    order = sorted(range(N), key=lambda i: (med[i], -point[i], int(rows[i]["dex"])))
    return {int(rows[i]["dex"]): pos for pos, i in enumerate(order, start=1)}


def load_cf(path: Path = CF_CSV) -> tuple[dict[tuple[int, str, str], float], dict[tuple[int, str, str], float]]:
    """(dex, move, mod key or '') -> median seconds, and the same key -> composite score.

    Seconds are the protocol check: they must match start_noshop_s and best_median_s.
    The published rank orders the sim score (time times saturating damage and kill rates).
    A bench from before that score has no column; the score map then copies the seconds.
    """
    if not path.exists():
        raise SystemExit(f"falta {path.relative_to(sf.ROOT)}; córrelo con simulator/counterfactual_bench.py")
    seconds: dict[tuple[int, str, str], float] = {}
    scores: dict[tuple[int, str, str], float] = {}
    for r in csv.DictReader(path.open(encoding="utf8")):
        key = (int(r["dex"]), r["move"], r["mods"].split("=")[0] if r["mods"] else "")
        seconds[key] = float(r["median_s"])
        raw = r.get("median_score")
        scores[key] = float(raw) if raw not in (None, "") else seconds[key]
    return seconds, scores


def published_scores(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Composite scores behind the definitive rank: repertoire opening, solo best, noshop group run.

    Same path as make_definitive.main. Rewrites melee_locked and repertoire_bans on `rows`.
    """
    starts = {int(r["dex"]): r for r in md.load_csv(sf.SIM / "g2p2" / "rank_200.csv")}
    sweep_rows = md.load_csv(SWEEP_CSV)
    solo_rows = md.load_csv(SOLO_SWEEP)
    winners = md.winner_by_dex(solo_rows)
    sweep_moves = {(int(r["dex"]), r["start"]): r for r in sweep_rows}
    start_s, slo, shi, best_s = md.sim_arrays(rows, starts, winners, sweep_moves, False, share_interval=True)[:4]
    opening = md.repertoire_opening(SWEEP_CSV)
    noshop, _display = md.apply_repertoire(rows, start_s, slo, shi, opening)
    return start_s, best_s, noshop


def records() -> dict[str, dict]:
    """The full facts records: summary_facts.base_records() plus drivers and the ungated rank."""
    rows = sf.ranking_rows()
    base = sf.base_records()
    cf_start_s, _cf_start_score = load_cf(CF_CSV)
    cf_best_s, cf_best_score = load_cf(SOLO_CF)
    sweep_s: dict[int, list[float]] = {}
    sweep_score: dict[int, list[float]] = {}
    for r in md.load_csv(SWEEP_CSV):
        d = int(r["dex"])
        sweep_s.setdefault(d, []).append(float(r["median_s"]))
        sweep_score.setdefault(d, []).append(md.row_metric(r, "median_score", "median_s"))
    solo: dict[int, list[dict]] = {}
    for r in md.load_csv(SOLO_SWEEP):
        if not owner_rules.allows_melee(int(r["dex"])) and r.get("kind") == "melee":
            continue
        solo.setdefault(int(r["dex"]), []).append(r)
    display_s = np.array([float(r["start_median_s"]) for r in rows])
    noshop_s = np.array([float(r["start_noshop_s"]) for r in rows])
    best_display = np.array([float(r["best_median_s"]) for r in rows])
    start_score, best_score, _noshop_score = published_scores(rows)
    model = Model(rows, start_score, best_score)
    ungated = ungated_ranks(rows)

    out = {}
    for i, r in enumerate(rows):
        d = int(r["dex"])
        start_mv, best_mv = r["start_move"], r["best_move"]
        # Opening counterfactuals stay on the group bench (seconds must match start_noshop_s,
        # score must match the noshop group score). Best-move counterfactuals are the solo bench.
        base_start = cf_start_s.get((d, start_mv, ""))
        base_best = cf_best_s.get((d, best_mv, ""))
        base_best_score = cf_best_score.get((d, best_mv, ""))
        # The stat bench is the previous engine. A baseline that does not reproduce this
        # ranking is not a measurement, so those drivers stay at zero instead of
        # quoting a frozen sheet.
        bench_ok = (
            base_start is not None and base_best is not None and base_best_score is not None
            and abs(base_start - noshop_s[i]) <= 1e-6
            and abs(base_best - best_display[i]) <= 1e-6
            and abs(base_best_score - best_score[i]) <= 1e-4
        )
        here = model.counterfactual(i)
        drivers = {}
        for key, factor in SIM_STATS.items():
            if not bench_ok:
                drivers[factor] = {"places": 0, "startS": 0.0, "bestS": 0.0}
                continue
            s2 = cf_start_s.get((d, start_mv, key))
            b2 = cf_best_s.get((d, best_mv, key))
            b2_score = cf_best_score.get((d, best_mv, key))
            if s2 is None:
                drivers[factor] = {"places": 0, "startS": 0.0, "bestS": 0.0}
                continue
            if b2 is None or b2_score is None:
                b2, b2_score = base_best, base_best_score
            cfr = model.counterfactual(i, best_s=b2_score)
            drivers[factor] = {"places": int(cfr - here), "startS": sf.r2(base_start - s2), "bestS": sf.r2(base_best - b2)}
        cand_s = statistics.median(sweep_s[d])
        cand_score = statistics.median(sweep_score[d])
        drivers["start_move"] = {"places": int(model.counterfactual(i, start_s=cand_score) - here),
                                 "startS": sf.r2(float(display_s[i]) - cand_s)}
        rest = [row for row in solo[d] if row["start"] != best_mv]
        runner = md.winner_by_dex(rest)[d] if rest else solo[d][0]
        runner_score = md.row_metric(runner, "median_score", "median_s")
        ref_best = base_best if base_best is not None else float(best_display[i])
        drivers["best_move"] = {"places": int(model.counterfactual(i, best_s=runner_score) - here),
                                "bestS": sf.r2(ref_best - float(runner["median_s"]))}
        for k in ("stats", "moves", "typedef"):
            drivers[k] = {"places": int(model.counterfactual(i, pillars={k: 0.5}) - here)}
        drivers["late"] = {"places": int(model.counterfactual(i, late=True) - here)}
        locked = r["melee_locked"] == "1"
        gated = r["stats_capped"] == "1" or r["types_capped"] == "1" or (locked and ungated[d] <= 30)
        drivers["gate"] = {"places": -(int(r["rank"]) - ungated[d]) if gated else 0}
        out[str(d)] = {**base[str(d)], "ungated": ungated[d], "drivers": drivers}
    return out


def table(recs: dict[str, dict]) -> pa.Table:
    cols: dict[str, list] = {k: [] for k in (
        "dex", "name", "name_en", "types", "tier", "rank", "rank_p10", "rank_p90",
        "speed_pct", "hp_pct", "attack_pct", "hitbox_r", "hitbox_median", "hitbox_smaller_pct",
        "typedef_pct", "super_pct", "attack_types",
        "start_move", "best_move", "group", "alts", "item", "cards",
        "drivers_up", "drivers_down", "claims", "record", "fp", "bfp")}
    for d, f in sorted(recs.items(), key=lambda kv: int(kv[0])):
        b = f["build"]
        for k, v in (
                ("dex", f["dex"]), ("name", f["name"]), ("name_en", f["nameEn"]), ("types", f["types"]),
                ("tier", f["tier"]), ("rank", f["rank"]), ("rank_p10", f["p10"]), ("rank_p90", f["p90"]),
                ("speed_pct", f["stats"]["spd"]["pct"]), ("hp_pct", f["stats"]["hp"]["pct"]),
                ("attack_pct", f["stats"]["atk"]["pct"]), ("hitbox_r", float(f["hitbox"]["r"])),
                ("hitbox_median", float(f["hitbox"]["median"])), ("hitbox_smaller_pct", f["hitbox"]["pctSmaller"]),
                ("typedef_pct", f["pillars"]["typedef"]), ("super_pct", f["matchup"]["superPct"]),
                ("attack_types", f["matchup"]["attackTypes"]),
                ("start_move", b["start"]["en"]), ("best_move", b["best"]["en"]),
                ("group", [m["en"] for m in b["group"]]), ("alts", [m["en"] for m in b["alts"]]),
                ("item", b["item"]["en"]), ("cards", [c["en"] for c in b["cards"]]),
                ("drivers_up", summaries.ranked_drivers(f, True)), ("drivers_down", summaries.ranked_drivers(f, False)),
                ("claims", json.dumps(summaries.claims(f), ensure_ascii=False)),
                ("record", json.dumps(f, ensure_ascii=False, sort_keys=True)),
                ("fp", sf.fingerprint(f)), ("bfp", sf.fingerprint(sf.base_of(f)))):
            cols[k].append(v)
    return pa.table(cols)


def parquet_bytes(t: pa.Table) -> bytes:
    buf = io.BytesIO()
    pq.write_table(t, buf, compression="zstd", compression_level=9, use_dictionary=True, write_statistics=False,
                   store_schema=False)
    return buf.getvalue()


def load(path: Path = OUT) -> dict[str, dict]:
    """dex (string) -> full facts record, from data/facts.parquet."""
    if not path.exists():
        raise SystemExit(f"falta {path.relative_to(sf.ROOT)}: python3 build/facts_export.py")
    t = pq.read_table(path, columns=["dex", "record"]).to_pydict()
    return {str(d): json.loads(r) for d, r in zip(t["dex"], t["record"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    data = parquet_bytes(table(records()))
    if args.check:
        if not OUT.exists() or OUT.read_bytes() != data:
            print(f"{OUT.relative_to(sf.ROOT)} está desactualizado: python3 build/facts_export.py", file=sys.stderr)
            return 1
        print("facts.parquet al día")
        return 0
    OUT.write_bytes(data)
    print(f"escrito {OUT.relative_to(sf.ROOT)} ({N} especies, {len(data) / 1e3:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
