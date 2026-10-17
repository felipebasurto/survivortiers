"""Stage 1 of the summaries: every species' facts record, with the rank drivers, in one parquet file.

    python3 build/facts_export.py            # writes data/facts.parquet
    python3 build/facts_export.py --check    # fails if data/facts.parquet is not what the data gives today

Needs numpy and pyarrow (the hosting build does not; catalog.py only uses the stdlib part, summary_facts.py).
Deterministic: same inputs, same bytes. One row per species, sorted by dex. Flat columns for a quick look
(percentiles, hitbox, build names, drivers), `claims` (JSON: every claim key that holds for that species with
what it means and plain wording, which is all a writer needs), `record` (JSON: the full facts record the
validator uses) and `fp` / `bfp` (hash of the full record / of the record without drivers).

Drivers. The published order is a weighted geometric mean of percentiles: sheet 45 (pillars stats 45, moves 25,
type defence 15, size 15), early sim 30 (start move 10, best move 45) and late game 25 (build/make_definitive.py).
For each factor the record holds how many places the species would move if only that factor were at the
population median, everything else fixed, on that same point score:
  hitbox, speed, hp, attack  re-simulated with that stat at the median (simulator/counterfactual_bench.py,
                             results/fixed_group/counterfactuals_g2p2.csv, same seeds and flags as the rank).
                             hitbox also sets the size pillar to the median radius.
  start_move                 that sim median replaced by the median over every start the species can learn
                             (results/fixed_group/g2p2/starter_sweep.csv).
  best_move                  that sim median replaced by its second best start in the same sweep: what the move
                             itself adds. (Against the median of its own moves it would lift every species.)
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
import summaries  # noqa: E402
import summary_facts as sf  # noqa: E402

OUT = sf.DATA / "facts.parquet"
CF_CSV = sf.SIM / "counterfactuals_g2p2.csv"
SWEEP_CSV = sf.SIM / "g2p2" / "starter_sweep.csv"
N = sf.N
PILLAR_W = {"stats": 45, "moves": 25, "typedef": 15, "size": 15}
SIM_STATS = {"r": "hitbox", "spd": "speed", "hp": "hp", "atk": "attack"}


def rank_among(value: float, others: np.ndarray) -> int:
    """1 + how many of the other species score higher."""
    return 1 + int((others > value).sum())


class Model:
    """The published point score (make_definitive.draw without the noise) and single-species counterfactuals."""

    def __init__(self, rows: list[dict], start_s: np.ndarray, best_s: np.ndarray):
        self.start_s, self.best_s = start_s, best_s
        self.pil = np.array([[float(r["pct_" + k]) for k in PILLAR_W] for r in rows])
        self.w = np.array(list(PILLAR_W.values()), dtype=float)
        self.sheet_score = self._sheet(self.pil)
        self.sheet_rank = np.array([int(r["rank_sheet"]) for r in rows], dtype=float)
        v4m = np.array([int(r["rank_v4_max"]) for r in rows], dtype=float)
        v4f = np.array([int(r["rank_v4_fresh"]) for r in rows], dtype=float)
        self.early_score = self._early_score(md.ranks_of(start_s), md.ranks_of(best_s))
        self.early_rank = md.ranks_of(self.early_score)
        self.late_score = np.exp((2 / 3) * np.log(md.pct(v4m)) + (1 / 3) * np.log(md.pct(v4f)))
        self.late_rank = md.ranks_of(self.late_score)
        self.point = self._point(self.sheet_rank, self.early_rank, self.late_rank)

    def _sheet(self, pil: np.ndarray) -> np.ndarray:
        return np.exp((np.log(np.maximum(pil, 1e-9)) * self.w).sum(-1) / self.w.sum())

    @staticmethod
    def _early_score(rs, rb):
        return np.exp((10 * np.log(md.pct(rs)) + 45 * np.log(md.pct(rb))) / 55)

    @staticmethod
    def _point(sheet, early, late):
        return np.exp((45 * np.log(md.pct(sheet)) + 30 * np.log(md.pct(early)) + 25 * np.log(md.pct(late))) / 100)

    def counterfactual(self, i: int, start_s=None, best_s=None, pillars: dict | None = None, late=False) -> int:
        """Point rank of species i with only the given pieces changed."""
        others = np.arange(N) != i
        sheet = self.sheet_rank[i]
        if pillars:
            pil = self.pil[i].copy()
            for k, v in pillars.items():
                pil[list(PILLAR_W).index(k)] = v
            mine = rank_among(float(self._sheet(pil)), self.sheet_score[others])
            sheet = sheet + mine - rank_among(float(self.sheet_score[i]), self.sheet_score[others])
        early = self.early_rank[i]
        if start_s is not None or best_s is not None:
            s = self.start_s[i] if start_s is None else start_s
            b = self.best_s[i] if best_s is None else best_s
            rs = rank_among(s, self.start_s[others])
            rb = rank_among(b, self.best_s[others])
            early = rank_among(float(self._early_score(rs, rb)), self.early_score[others])
        lr = self.late_rank[i]
        if late:
            lr = rank_among(float(np.exp(np.log(md.pct(483.5)))), self.late_score[others])
        score = float(self._point(sheet, early, lr))
        return rank_among(score, self.point[others])


def ungated_ranks(rows: list[dict]) -> dict[int, int]:
    """Position of each species before the tier gates, as make_definitive.main orders it."""
    starts = {int(r["dex"]): r for r in md.load_csv(sf.SIM / "g2p2" / "rank_200.csv")}
    sweep = md.load_csv(SWEEP_CSV)
    winners = md.winner_by_dex(sweep)
    sweep_moves = {(int(r["dex"]), r["start"]): r for r in sweep}
    arrays = md.sim_arrays(rows, starts, winners, sweep_moves, False)
    start_s, slo, shi, best_s, blo, bhi, same = arrays[:7]
    sheet = np.array([int(r["rank_sheet"]) for r in rows], dtype=float)
    v4m = np.array([int(r["rank_v4_max"]) for r in rows], dtype=float)
    v4f = np.array([int(r["rank_v4_fresh"]) for r in rows], dtype=float)
    _, _, point, fr = md.draw(start_s, slo, shi, best_s, blo, bhi, same, sheet, v4m, v4f)
    med = np.median(fr, axis=0)
    order = sorted(range(N), key=lambda i: (med[i], -point[i], int(rows[i]["dex"])))
    return {int(rows[i]["dex"]): pos for pos, i in enumerate(order, start=1)}


def load_cf() -> dict[tuple[int, str, str], float]:
    """(dex, move, mod key or '') -> median seconds."""
    if not CF_CSV.exists():
        raise SystemExit(f"falta {CF_CSV.relative_to(sf.ROOT)}; córrelo con simulator/counterfactual_bench.py")
    out = {}
    for r in csv.DictReader(CF_CSV.open(encoding="utf8")):
        key = r["mods"].split("=")[0] if r["mods"] else ""
        out[(int(r["dex"]), r["move"], key)] = float(r["median_s"])
    return out


def records() -> dict[str, dict]:
    """The full facts records: summary_facts.base_records() plus drivers and the ungated rank."""
    rows = sf.ranking_rows()
    base = sf.base_records()
    px = {p["dex"]: p for p in json.loads((sf.DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    cf = load_cf()
    sweep: dict[int, list[float]] = {}
    for r in md.load_csv(SWEEP_CSV):
        sweep.setdefault(int(r["dex"]), []).append(float(r["median_s"]))
    start_s = np.array([float(r["start_median_s"]) for r in rows])
    best_s = np.array([float(r["best_median_s"]) for r in rows])
    model = Model(rows, start_s, best_s)
    ungated = ungated_ranks(rows)
    med_r = statistics.median(px[int(r["dex"])]["body_radius"] for r in rows)
    med_size = float(np.median([float(r["pct_size"]) for r in rows if px[int(r["dex"])]["body_radius"] == med_r]))

    out = {}
    for i, r in enumerate(rows):
        d = int(r["dex"])
        start_mv, best_mv = r["start_move"], r["best_move"]
        base_start, base_best = cf[(d, start_mv, "")], cf[(d, best_mv, "")]
        if abs(base_start - start_s[i]) > 1e-9 or abs(base_best - best_s[i]) > 1e-9:
            raise SystemExit(f"{d}: la sim de contrafactuales no reproduce el ranking ({base_start} / {start_s[i]}, "
                             f"{base_best} / {best_s[i]})")
        here = model.counterfactual(i)
        drivers = {}
        for key, factor in SIM_STATS.items():
            s2, b2 = cf.get((d, start_mv, key)), cf.get((d, best_mv, key))
            if s2 is None:  # already at the median
                drivers[factor] = {"places": 0, "startS": 0.0, "bestS": 0.0}
                continue
            pil = {"size": med_size} if key == "r" else None
            cfr = model.counterfactual(i, start_s=s2, best_s=b2, pillars=pil)
            drivers[factor] = {"places": int(cfr - here), "startS": sf.r2(base_start - s2), "bestS": sf.r2(base_best - b2)}
        cand = statistics.median(sweep[d])
        drivers["start_move"] = {"places": int(model.counterfactual(i, start_s=cand) - here), "startS": sf.r2(base_start - cand)}
        runner_up = sorted(sweep[d])[-2] if len(sweep[d]) > 1 else base_best
        drivers["best_move"] = {"places": int(model.counterfactual(i, best_s=runner_up) - here),
                                "bestS": sf.r2(base_best - runner_up)}
        for k in ("stats", "moves", "typedef"):
            drivers[k] = {"places": int(model.counterfactual(i, pillars={k: 0.5}) - here)}
        drivers["late"] = {"places": int(model.counterfactual(i, late=True) - here)}
        gated = r["stats_capped"] == "1" or r["types_capped"] == "1" or (r["melee_start"] == "1" and ungated[d] <= 30)
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
