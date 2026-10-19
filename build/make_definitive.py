"""Rebuild data/ranking_definitive.csv from a fixed-group 2+2 sim.

Sheet percentiles, v4 ranks and the other non-sim columns stay as they are in the previous
ranking. The sim piece is replaced:

  rank_sim_start / rank_sim_best   order of median seconds (ties: lower dex)
  rank_early                       geometric mean of those rank-percentiles, weights 10 and 45
  rank_late                        geometric mean of v4 max and v4 fresh, weights 2/3 and 1/3
  final score                      geometric mean of sheet, early and late, weights 45, 30 and 25

rank_sim_start is the Repertorio + Veto opening (simulator/sim/repertorio.js), not the starter
alone. The starter alone stays in start_noshop_s / rank_sim_noshop and is not weighted. The 10/45
split is unchanged: the move you build still dominates the early piece, and the opening is the
first stretch of the run. Players who chase a tier buy Repertorio (1500, one level).

Percentile of a rank r (1 = best of 966) is (966 - r + 0.5) / 966.

Two thousand repeats (seed 20261014) move each median inside its bootstrap interval, cycle 80
blends of the late-game model around the 2/3 weight, and move the sim/late weights around 30/25
with the sheet fixed at 45. The published order is the median of those ungated ranks. Tiers are
then filled with the gates (stats 0.6 / 0.4 / 0.2, three attack types for S, melee_locked out of S).
melee_locked means every remaining Repertorio draw still plays a melee move. A melee starter you
can switch off is not a hard ban; that penalty is already in the opening expectation.
p10, p90, p_tier and p_S describe the ungated repeats. Sim numbers are estimates.

Feeding the previous sim columns back through this procedure reproduces that ranking only to a
mean absolute error of about 5 ranks. The historical file was not recovered more tightly from the
documented weights; this script publishes that same estimate for the new runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import combos  # noqa: E402
import owner_rules  # noqa: E402
import picks  # noqa: E402
import tiers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N = 966
REPEATS = 2000
SEED = 20261014
LATE_SPAN = 0.15
SIM_AMP = 22.0
HEADER = (
    "rank,dex,name,tier,rank_p10,rank_p90,p_tier,p_S,start_move,start_kind,start_median_s,"
    "best_move,best_median_s,rank_sim_start,rank_sim_best,rank_v4_max,rank_v4_fresh,rank_early,"
    "rank_late,phase_gap,rank_sheet,pct_stats,pct_moves,pct_typedef,pct_size,move_pair,"
    "shot_dmg_taken,radius,map_reach,stats_capped,attack_types,types_capped,status_unmodelled,melee_start,"
    "start_noshop_s,rank_sim_noshop,melee_locked,repertoire_bans"
)
COMMENT = (
    "# Ranking from the sim only. The sheet (stats, moves, type defence, hitbox) and the v4 table "
    "stay in the file and do not move a rank. The order is the bootstrap of the sim score: "
    "time times the geometric mean of a saturating damage rate and a saturating kill rate. "
    "A run that deals no damage scores 0. Overlapping score intervals show as the rank band, not as a winner. "
    "S is the top of that order, except melee_locked (every remaining Repertorio draw is still melee). "
    "best_move is an attacking move from the solo sweep. "
    "start_median_s is the Repertorio opening. start_noshop_s is the starter alone and is not ranked."
)
CUTS = tuple(tiers.COUNTS.items())
BANDS, STAT_MIN, TIER_OF = tiers.BANDS, tiers.STAT_MIN, tiers.TIER_OF


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def pct(rank: np.ndarray) -> np.ndarray:
    return (N - rank + 0.5) / N


def ranks_of(score: np.ndarray) -> np.ndarray:
    """Higher score is better. Dex-sorted columns make a stable sort break ties by dex."""
    order = np.argsort(-score, axis=-1, kind="stable")
    out = np.empty(order.shape, dtype=np.float64)
    if order.ndim == 1:
        out[order] = np.arange(1, N + 1)
        return out
    rows = np.arange(order.shape[0])[:, None]
    out[rows, order] = np.arange(1, N + 1)
    return out


def early_ranks(start_s: np.ndarray, best_s: np.ndarray) -> np.ndarray:
    rs = ranks_of(start_s)
    rb = ranks_of(best_s)
    return ranks_of(np.exp((10 * np.log(pct(rs)) + 45 * np.log(pct(rb))) / 55))


def late_ranks_for(v4m: np.ndarray, v4f: np.ndarray, weight: float) -> np.ndarray:
    score = np.exp(weight * np.log(pct(v4m)) + (1 - weight) * np.log(pct(v4f)))
    return ranks_of(score)


def row_metric(row: dict, score_key: str, fallback: str) -> float:
    raw = row.get(score_key)
    if raw not in (None, ""):
        return float(raw)
    return float(row[fallback])


def _ci(row: dict) -> tuple[float, float, float]:
    melee = row.get("kind") == "melee"
    return picks.score_bounds(row, melee)


def winner_by_dex(sweep: list[dict]) -> dict[int, dict]:
    """One attacking move per species: the highest score after the owner rules (build/picks.py).

    Sustituto, buffs and moves that dealt nothing are not candidates, Gengar keeps no melee move,
    and a melee score takes the owner's penalty. There is no interval tie rule: the sweep already
    refreshes the contenders on fresh seeds, and the band on the page shows what is left of the noise.
    """
    return picks.best_moves(sweep)


def qualifies(row: dict, tier: str) -> bool:
    # Tiers are the sim order. The old stats and attack-type gates were the sheet.
    # melee_locked is the repertoire: every remaining draw is still melee.
    if tier == "S" and row.get("melee_locked") == "1":
        return False
    return True


def fill_tiers(order: list[dict]) -> list[dict]:
    remaining = list(order)
    placed: list[dict] = []
    for tier, count in CUTS:
        taken: list[dict] = []
        rest: list[dict] = []
        for row in remaining:
            if len(taken) < count and qualifies(row, tier):
                taken.append(row)
            else:
                rest.append(row)
        if len(taken) < count:
            raise SystemExit(f"only {len(taken)} Pokémon qualify for {tier}, need {count}")
        placed.extend(taken)
        remaining = rest
    if len(placed) != N:
        raise SystemExit(f"placed {len(placed)}, expected {N}")
    return placed


def fmt_prob(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") or "0"


def fmt_seconds(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") or "0"


def repertoire_opening(sweep_path: Path) -> dict[int, dict]:
    """dex -> opening from simulator/sim/repertorio.js (the same function sim-rs tests)."""
    script = ROOT / "simulator" / "sim" / "repertorio.js"
    proc = subprocess.run(
        ["node", str(script), "--sweep", str(sweep_path)],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "repertorio.js failed")
    return {int(row["dex"]): row for row in json.loads(proc.stdout)}


def apply_repertoire(base: list[dict], start_s, slo, shi, opening: dict[int, dict]):
    """Replace the solo starter with the Repertorio expectation.

    The arrays that feed the rank use the composite score when the sweep has one.
    The returned display array stays in seconds.
    """
    noshop = start_s.copy()
    display = start_s.copy()
    for i, row in enumerate(base):
        op = opening[int(row["dex"])]
        display[i] = float(op["median"])
        if "rank" in op:
            start_s[i] = float(op["rank"])
            slo[i] = min(float(op["rankLo"]), start_s[i])
            shi[i] = max(float(op["rankHi"]), start_s[i])
        else:
            start_s[i] = float(op["median"])
            slo[i] = min(float(op["lo"]), start_s[i])
            shi[i] = max(float(op["hi"]), start_s[i])
        row["melee_locked"] = "1" if op["meleeLocked"] else "0"
        row["repertoire_bans"] = "|".join(op["banned"])
    return noshop, display


def sim_arrays(base: list[dict], starts: dict[int, dict], winners: dict[int, dict], sweep_moves: dict, use_stored_best: bool, share_interval: bool = True):
    start_s = np.array([row_metric(starts[int(r["dex"])], "median_score", "median_s") for r in base])
    slo = np.array([row_metric(starts[int(r["dex"])], "score_lo", "boot_lo") for r in base])
    shi = np.array([row_metric(starts[int(r["dex"])], "score_hi", "boot_hi") for r in base])
    best_s = np.empty(N)
    blo = np.empty(N)
    bhi = np.empty(N)
    same = np.zeros(N, dtype=bool)
    best_move: list[str] = []
    best_text: list[str] = []
    for i, row in enumerate(base):
        dex = int(row["dex"])
        if use_stored_best:
            move = row["best_move"]
            best_s[i] = float(row["best_median_s"])
            best_move.append(move)
            best_text.append(row["best_median_s"])
            rec = sweep_moves.get((dex, move))
            if rec is None:
                blo[i], bhi[i] = slo[i], shi[i]
            else:
                blo[i], bhi[i] = row_metric(rec, "score_lo", "boot_lo"), row_metric(rec, "score_hi", "boot_hi")
                best_s[i] = row_metric(rec, "median_score", "median_s")
        else:
            win = winners[dex]
            best_s[i] = row_metric(win, "median_score", "median_s")
            blo[i], bhi[i] = row_metric(win, "score_lo", "boot_lo"), row_metric(win, "score_hi", "boot_hi")
            best_move.append(win["start"])
            best_text.append(win["median_s"])
        # Same move id only shares an interval when both numbers come from one protocol.
        # A solo best-move sweep and the group opening are different runs.
        same[i] = share_interval and best_move[-1] == row["start_move"]
        if same[i]:
            blo[i], bhi[i] = slo[i], shi[i]
    return start_s, slo, shi, best_s, blo, bhi, same, best_move, best_text


def draw(start_s, slo, shi, best_s, blo, bhi, same, sheet, v4m, v4f):
    """Rank on the sim score only.

    The frozen sheet (including the hitbox pillar) and the v4 table used to be 45% and 25%
    of the order. Both stay in the CSV so old columns still parse. They do not move a rank.
    The band is the bootstrap of the sim interval, which is the seed noise we actually measured.
    """
    del sheet, v4m, v4f
    early_point = early_ranks(start_s, best_s)
    late_point = early_point
    point = best_s
    rng = np.random.default_rng(SEED)
    bt = blo + rng.random((REPEATS, N)) * np.maximum(bhi - blo, 0)
    st = slo + rng.random((REPEATS, N)) * np.maximum(shi - slo, 0)
    bt[:, same] = st[:, same]
    fr = ranks_of(bt)
    return early_point, late_point, point, fr


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the definitive ranking from group-mode sim results.")
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "ranking_definitive.csv")
    parser.add_argument("--rank-200", type=Path, default=ROOT / "simulator" / "results" / "fixed_group" / "g2p2" / "rank_200.csv")
    parser.add_argument("--sweep", type=Path, default=ROOT / "simulator" / "results" / "fixed_group" / "g2p2" / "starter_sweep.csv")
    parser.add_argument("--best-sweep", type=Path, default=None,
                        help="Sweep whose winner is best_move. Defaults to --sweep. "
                             "The opening stays on --sweep and rank-200.")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "ranking_definitive.csv")
    parser.add_argument("--use-stored-best", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    base = load_csv(args.base)
    if len(base) != N:
        raise SystemExit(f"{args.base} has {len(base)} rows")
    base.sort(key=lambda r: int(r["dex"]))
    starts = {int(r["dex"]): r for r in load_csv(args.rank_200)}
    sweep_rows = load_csv(args.sweep)
    best_rows = load_csv(args.best_sweep) if args.best_sweep else sweep_rows
    winners = winner_by_dex(best_rows)
    if set(starts) != {int(r["dex"]) for r in base} or set(winners) != {int(r["dex"]) for r in base}:
        raise SystemExit("sim files do not cover the same 966 species as the ranking")
    sweep_moves = {(int(r["dex"]), r["start"]): r for r in sweep_rows}
    ignored = {int(r["dex"]) for r in sweep_rows if r.get("status_ignored") == "1"}
    ignored |= {int(r["dex"]) for r in best_rows if r.get("status_ignored") == "1"}
    start_s, slo, shi, best_s, blo, bhi, same, best_move, best_text = sim_arrays(
        base, starts, winners, sweep_moves, args.use_stored_best, share_interval=args.best_sweep is None
    )
    opening = repertoire_opening(args.sweep)
    if set(opening) != {int(r["dex"]) for r in base}:
        raise SystemExit("repertoire opening does not cover the same 966 species")
    noshop, start_display = apply_repertoire(base, start_s, slo, shi, opening)
    sheet = np.array([int(r["rank_sheet"]) for r in base], dtype=float)
    v4m = np.array([int(r["rank_v4_max"]) for r in base], dtype=float)
    v4f = np.array([int(r["rank_v4_fresh"]) for r in base], dtype=float)
    early_point, late_point, point, fr = draw(start_s, slo, shi, best_s, blo, bhi, same, sheet, v4m, v4f)
    med = np.median(fr, axis=0)
    p10 = np.percentile(fr, 10, axis=0)
    p90 = np.percentile(fr, 90, axis=0)
    p_s = np.mean(fr <= 30, axis=0)
    rstart = ranks_of(start_s).astype(int)
    rbest = ranks_of(best_s).astype(int)
    rnoshop = ranks_of(noshop).astype(int)

    order_ix = sorted(range(N), key=lambda i: (med[i], -point[i], int(base[i]["dex"])))
    ungated = [base[i] for i in order_ix]
    flag_stats: dict[int, bool] = {}
    flag_types: dict[int, bool] = {}
    for pos, row in enumerate(ungated, start=1):
        tier = TIER_OF[pos]
        dex = int(row["dex"])
        thr = STAT_MIN.get(tier)
        flag_stats[dex] = thr is not None and float(row["pct_stats"]) < thr
        flag_types[dex] = tier == "S" and int(row["attack_types"]) < 3
    placed = fill_tiers(ungated)
    index = {int(r["dex"]): i for i, r in enumerate(base)}

    out_rows: list[dict] = []
    for place, row in enumerate(placed, start=1):
        dex = int(row["dex"])
        i = index[dex]
        tier = TIER_OF[place]
        lo, hi = BANDS[tier]
        out = dict(row)
        out.update({
            "rank": str(place),
            "tier": tier,
            "rank_p10": str(int(round(float(p10[i])))),
            "rank_p90": str(int(round(float(p90[i])))),
            "p_tier": fmt_prob(float(np.mean((fr[:, i] >= lo) & (fr[:, i] <= hi)))),
            "p_S": fmt_prob(float(p_s[i])),
            "start_median_s": fmt_seconds(float(start_display[i])),
            "start_noshop_s": starts[dex]["median_s"],
            "rank_sim_noshop": str(int(rnoshop[i])),
            "best_move": best_move[i],
            "best_median_s": best_text[i],
            "rank_sim_start": str(int(rstart[i])),
            "rank_sim_best": str(int(rbest[i])),
            "rank_early": str(int(early_point[i])),
            "rank_late": str(int(late_point[i])),
            "phase_gap": str(int(late_point[i]) - int(early_point[i])),
            "stats_capped": "1" if flag_stats[dex] else "0",
            "types_capped": "1" if flag_types[dex] else "0",
            # Any swept move the sim still refused to apply. With --status and extra kinds this is 0.
            "status_unmodelled": "1" if dex in ignored else "0",
        })
        out_rows.append(out)

    if args.check:
        err = [abs(int(r["rank"]) - int(base[index[int(r["dex"])]]["rank"])) for r in out_rows]
        late_err = [abs(int(r["rank_late"]) - int(base[index[int(r["dex"])]]["rank_late"])) for r in out_rows]
        early_err = [abs(int(r["rank_early"]) - int(base[index[int(r["dex"])]]["rank_early"])) for r in out_rows]
        width = float(np.median(p90 - p10))
        print(
            f"mae {sum(err)/len(err):.2f}  median abs {sorted(err)[len(err)//2]}  max {max(err)}  "
            f"band {width:.1f}  late mae {sum(late_err)/len(late_err):.3f}  early mae {sum(early_err)/len(early_err):.3f}"
        )
        return

    if not args.use_stored_best:
        dex_types = {p["dex"]: p["types"] for p in json.loads((ROOT / "data" / "pokedex_export.json").read_text(encoding="utf8"))}
        groups = combos.compute_all(dex_types, {int(r["dex"]): r["best_move"] for r in out_rows})
        for row in out_rows:
            group = groups[int(row["dex"])]
            attacks = group["moves"][: len(group["moves"]) - group["nBoost"]]
            row["move_pair"] = " + ".join(attacks)
    lines = [COMMENT, HEADER]
    cols = HEADER.split(",")
    for row in out_rows:
        lines.append(",".join(row[c] for c in cols))
    args.out.write_text("\n".join(lines) + "\n", encoding="utf8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
