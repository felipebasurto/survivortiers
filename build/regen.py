"""One command for the published data.

    python3 build/regen.py
    python3 build/regen.py --check

Rebuilds data/ranking_definitive.csv from the committed sim CSVs. --check writes
that rebuild to a temp file and diffs it. A default rebuild must match the file in git.

    python3 build/regen.py --sim

Reruns the engine first (release pokesim, Play bot, common seeds):

- rank, three disjoint blocks (seed0 0 / 100 / 200) for the S-tier check
- solo starter sweep (best move)
- group 2+2 starter sweep (Repertorio opening)
- pruned group search for every species

Then it rebuilds the ranking. facts.parquet and the ficha summaries are the next
step (`--facts`), then catalog.py and render.py.

pokedex_export.json and game_stats.json are extracts of the game at e868b5e
(`build/import_game_combat.py`, `build/export_game_stats.js`). move_tierlist_v4.csv
is the old analysis table; the rank does not read it. passive_sim.json is the
passive bench summary. Those are not produced by a default rebuild.
"""
from __future__ import annotations

import argparse
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator"
BIN = SIM / "sim-rs" / "target" / "release" / "pokesim"
FIXED = SIM / "results" / "fixed_group"


def pokesim(*args: str) -> None:
    subprocess.run([str(BIN), *args], cwd=SIM, check=True)


def rebuild(out: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "build" / "make_definitive.py"),
            "--rank-200",
            str(FIXED / "g2p2" / "rank_200.csv"),
            "--sweep",
            str(FIXED / "g2p2" / "starter_sweep.csv"),
            "--best-sweep",
            str(FIXED / "solo_sweep.csv"),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        check=True,
    )


def facts() -> None:
    subprocess.run([sys.executable, str(ROOT / "build" / "facts_export.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "build" / "write_summaries.py")], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the ranking from the engine.")
    parser.add_argument("--check", action="store_true", help="Fail if a rebuild differs from the committed CSV.")
    parser.add_argument("--sim", action="store_true", help="Rerun the starter sweep and the group search first.")
    parser.add_argument("--seeds", default="16")
    parser.add_argument("--facts", action="store_true", help="Rewrite facts.parquet and the summaries that no longer match.")
    args = parser.parse_args()

    if args.sim:
        if not BIN.exists():
            subprocess.run(
                ["cargo", "build", "--release", "--manifest-path", str(SIM / "sim-rs" / "Cargo.toml")],
                check=True,
            )
        FIXED.mkdir(parents=True, exist_ok=True)
        (FIXED / "g2p2").mkdir(parents=True, exist_ok=True)
        common = ["--seeds", args.seeds, "--seconds", "900", "--status", "--terrain", "--xkinds"]
        for seed0, name in (("0", "rank_200.csv"), ("100", "rank_b.csv"), ("200", "rank_c.csv")):
            dest = FIXED / "g2p2" / name if seed0 == "0" else FIXED / "stage2" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            pokesim("rank", *common, "--group", "2+2", "--seed0", seed0, "--out", str(dest))
        pokesim("sweep", *common, "--no-synergy", "--out", str(FIXED / "solo_out"))
        solo_csv = FIXED / "solo_out" / "starter_sweep.csv"
        if solo_csv.exists():
            (FIXED / "solo_sweep.csv").write_bytes(solo_csv.read_bytes())
        pokesim("sweep", *common, "--group", "2+2", "--out", str(FIXED / "g2p2_out"))
        g2 = FIXED / "g2p2_out" / "starter_sweep.csv"
        if g2.exists():
            (FIXED / "g2p2" / "starter_sweep.csv").write_bytes(g2.read_bytes())
        pokesim("synergy", "--seeds", args.seeds, "--seconds", "900", "--out", str(FIXED / "group_search.csv"))

    ranking = ROOT / "data" / "ranking_definitive.csv"
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ranking.csv"
            rebuild(out)
            if not filecmp.cmp(out, ranking, shallow=False):
                raise SystemExit("ranking_definitive.csv does not match a rebuild from the committed sim CSVs")
        print("ranking matches the committed sim CSVs")
        return

    rebuild(ranking)
    print(f"wrote {ranking}")
    if args.facts:
        facts()


if __name__ == "__main__":
    main()
