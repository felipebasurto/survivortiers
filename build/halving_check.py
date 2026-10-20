"""Check the successive-halving cut of the group screen against the full screen.

    python3 build/halving_check.py            # full-screen sample, then the rule grid

The screen runs every group at 4 seeds (`group_screen_a.csv`; no script in the repo writes it any more). Only the
groups that pass the cut get the full 16 seeds. A survivor's row is the row the full screen
would give, because the seeds are the same. The cut can still drop a group the full screen
would have shortlisted, so this script checks that on a random sample of species:

1. run every group of the sampled species at 16 seeds (the full screen, for those species)
2. for each cut rule, keep the survivors from the 4-seed rows and compare the picks (the best
   PER_SHAPE groups per species and shape, as `picks.shortlist_groups`) with the full screen

A rule passes when every sampled species and shape keeps the same picks. The cost of a rule
is the number of matches it runs, next to the full 16-seed screen of every group.
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator"
BIN = SIM / "sim-rs" / "target" / "release" / "pokesim"
FIXED = SIM / "results" / "fixed_group"
SHORT_A = FIXED / "group_screen_a.csv"
WORK = FIXED / "halving"

PER_SHAPE = 2
SHORT_SEEDS = 4
FULL_SEEDS = 16
GRID_FRAC = (0.2, 0.25, 0.3, 0.35, 0.4)
GRID_MIN = (2, 3, 4)

Key = tuple[int, str]


def picks_by_shape(rows: list[dict]) -> dict[Key, frozenset[str]]:
    pools: dict[Key, list[dict]] = defaultdict(list)
    for row in rows:
        if picks.group_ok(row["group"]):
            pools[(int(row["dex"]), picks.shape_of(row["group"]))].append(row)
    return {
        key: frozenset(r["group"] for r in sorted(pool, key=picks.group_order)[:PER_SHAPE])
        for key, pool in pools.items()
    }


def sample_species(rows: list[dict], count: int, seed: int) -> set[int]:
    dexes = sorted({int(r["dex"]) for r in rows})
    return set(random.Random(seed).sample(dexes, min(count, len(dexes))))


def run_full_sample(only: list[str]) -> list[dict]:
    WORK.mkdir(parents=True, exist_ok=True)
    only_file = WORK / "sample_only.txt"
    only_file.write_text("\n".join(only) + "\n", encoding="utf8")
    out = WORK / "sample_full16.csv"
    subprocess.run(
        [str(BIN), "synergy", "--seeds", str(FULL_SEEDS), "--seconds", "900", "--partners", str(FIXED / "solo_screen.csv"),
         "--only", str(only_file), "--out", str(out)],
        cwd=SIM,
        check=True,
    )
    return picks.load_rows(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", type=int, default=120, help="species in the full 16-seed sample")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    short = picks.load_rows(SHORT_A)
    dex_set = sample_species(short, args.species, args.seed)
    only = [
        f"{r['dex']}|{r['group']}"
        for r in short
        if int(r["dex"]) in dex_set and picks.group_ok(r["group"])
    ]
    print(f"sample: {len(dex_set)} species, {len(only)} groups at {FULL_SEEDS} seeds", flush=True)

    full = run_full_sample(only)
    truth = {k: v for k, v in picks_by_shape(full).items() if k[0] in dex_set}
    print(f"full-screen picks: {len(truth)} (species, shape) pairs", flush=True)

    sample_short = [r for r in short if int(r["dex"]) in dex_set]
    short_matches = len(short) * SHORT_SEEDS
    full_matches = len(short) * FULL_SEEDS
    print("frac  min_keep  bad_species  bad_pairs  survivors_all  est_matches  est_speedup", flush=True)
    for frac in GRID_FRAC:
        for min_keep in GRID_MIN:
            keep = set(picks.halving_keep(sample_short, frac, min_keep))
            kept = [r for r in full if (r["dex"], r["group"]) in keep]
            got = {k: v for k, v in picks_by_shape(kept).items() if k[0] in dex_set}
            differing = {k for k in set(truth) | set(got) if truth.get(k, frozenset()) != got.get(k, frozenset())}
            bad_species = {k[0] for k in differing}
            survivors_all = len(picks.halving_keep(short, frac, min_keep))
            est = short_matches + survivors_all * FULL_SEEDS
            print(
                f"{frac:4.2f}  {min_keep:8d}  {len(bad_species):11d}  {len(differing):9d}  {survivors_all:13d}"
                f"  {est:11d}  {full_matches / est:10.2f}x",
                flush=True,
            )


if __name__ == "__main__":
    main()
