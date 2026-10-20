"""One command for the published data.

    python3 build/regen.py --check

Rebuilds data/ranking_definitive.csv from the committed sim CSVs into a temp file and
diffs it with the committed one. A default rebuild must match the file in git.

    python3 build/regen.py            # rewrite data/ranking_definitive.csv
    python3 build/regen.py --facts    # then facts.parquet and the summaries

    python3 build/regen.py --sim      # rerun the engine, in this order

The order matters: the group search ranks partners from the solo sweep.

1. solo screen    every simulated pool move as a start, 16 seeds (partners for step 3)
2. solo refine    each species' best 3 attacks on fresh seeds (selection and report use
                  different seeds, so the winner's curse stays out of the numbers)
3. solo contend   the best 2 attacks of the top species again on many more seeds
4. group screen   every searched group, 16 seeds (2 or 3 attacks of either category, each
                  with every attack buff that raises one of them and/or Fortaleza or Agilidad)
5. group refine   the best 2 groups of each shape (picks.shape_of) on fresh seeds
6. start sweep    every pool move as the start of a 2+2 group, 16 seeds (Repertorio opening)
7. start rank     the game's start move, 16 seeds, three disjoint blocks

A stage whose output exists is skipped unless --force. --from STAGE reruns that stage and
the ones after it. Stages are named in STAGES.

pokedex_export.json and game_stats.json are extracts of the game
(`build/import_game_combat.py`, `build/export_game_stats.js`, both read the game repo at
`legal.GAME_COMMIT`). move_tierlist_v4.csv is the analysis table; the rank does not read
it. passive_sim.json is the passive bench summary. Those are not produced by a default
rebuild.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds  # noqa: E402
import picks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator"
BIN = SIM / "sim-rs" / "target" / "release" / "pokesim"
FIXED = SIM / "results" / "fixed_group"

SCREEN_SEEDS = 16
SOLO_REFINE_SEEDS = 128
SOLO_REFINE_TOP = 3
SOLO_SEED0 = 1000
CONTEND_SEEDS = 512
CONTEND_SPECIES = 120
CONTEND_MOVES = 2
CONTEND_SEED0 = 3000
GROUP_REFINE_SEEDS = 96
GROUP_REFINE_PER_SHAPE = picks.REFINE_PER_SHAPE
GROUP_SEED0 = 1000
START_SEEDS = 16
COMMON = ["--seconds", "900", "--status", "--terrain", "--xkinds"]

SOLO_SCREEN = FIXED / "solo_screen.csv"
SOLO_REFINE = FIXED / "solo_refine.csv"
SOLO_CONTEND = FIXED / "solo_contend.csv"
SOLO_SWEEP = FIXED / "solo_sweep.csv"
GROUP_SCREEN = FIXED / "group_screen.csv"
GROUP_SEARCH = FIXED / "group_search.csv"
START_SWEEP = FIXED / "g2p2" / "starter_sweep.csv"
START_RANK = FIXED / "g2p2" / "rank_200.csv"
START_BLOCKS = ((FIXED / "stage2" / "rank_b.csv", "100"), (FIXED / "stage2" / "rank_c.csv", "200"))



def pokesim(*args: str) -> None:
    subprocess.run([str(BIN), *args], cwd=SIM, check=True)


def rel(path: Path) -> str:
    return str(path.relative_to(SIM))


def write_only(path: Path, keys: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sorted(set(keys))) + "\n", encoding="utf8")
    return path


def write_rows(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def header_of(path: Path) -> list[str]:
    with path.open(encoding="utf8") as f:
        return next(csv.reader(line for line in f if not line.startswith("#")))


def solo_screen() -> None:
    out = FIXED / "solo_screen_out"
    pokesim("sweep", *COMMON, "--seeds", str(SCREEN_SEEDS), "--no-synergy", "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_SCREEN)


def solo_refine() -> None:
    short = picks.shortlist_moves(picks.load_rows(SOLO_SCREEN), SOLO_REFINE_TOP)
    only = write_only(FIXED / "solo_refine_only.txt", [f"{d}|{r['start']}" for d, rows in short.items() for r in rows])
    out = FIXED / "solo_refine_out"
    pokesim("sweep", *COMMON, "--seeds", str(SOLO_REFINE_SEEDS), "--seed0", str(SOLO_SEED0), "--no-synergy",
            "--only", rel(only), "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_REFINE)


def contenders() -> dict[int, list[dict]]:
    best = picks.best_moves(picks.load_rows(SOLO_REFINE))
    top = sorted(best.values(), key=lambda r: picks.move_order(r))[:CONTEND_SPECIES]
    by_dex = picks.shortlist_moves(picks.load_rows(SOLO_REFINE), CONTEND_MOVES)
    return {int(r["dex"]): by_dex[int(r["dex"])] for r in top}


def solo_contend() -> None:
    chosen = contenders()
    only = write_only(FIXED / "solo_contend_only.txt", [f"{d}|{r['start']}" for d, rows in chosen.items() for r in rows])
    out = FIXED / "solo_contend_out"
    pokesim("sweep", *COMMON, "--seeds", str(CONTEND_SEEDS), "--seed0", str(CONTEND_SEED0), "--no-synergy",
            "--only", rel(only), "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_CONTEND)
    merge_solo(set(chosen))


def merge_solo(contend: set[int]) -> None:
    """The published solo sweep: the refine rows, with the contenders' rows replaced by the
    many-seed rows of their best moves. A species never mixes seed counts."""
    refine = picks.load_rows(SOLO_REFINE)
    contend_rows = picks.load_rows(SOLO_CONTEND)
    rows = [r for r in refine if int(r["dex"]) not in contend] + contend_rows
    rows.sort(key=lambda r: (int(r["dex"]), r["start"]))
    write_rows(SOLO_SWEEP, header_of(SOLO_CONTEND), rows)


def group_screen() -> None:
    pokesim("synergy", "--seeds", str(SCREEN_SEEDS), "--seconds", "900", "--partners", rel(SOLO_SCREEN),
            "--out", rel(GROUP_SCREEN))


def group_refine() -> None:
    short = picks.shortlist_groups(picks.load_rows(GROUP_SCREEN), GROUP_REFINE_PER_SHAPE)
    only = write_only(FIXED / "group_refine_only.txt", [f"{d}|{r['group']}" for d, rows in short.items() for r in rows])
    pokesim("synergy", "--seeds", str(GROUP_REFINE_SEEDS), "--seed0", str(GROUP_SEED0), "--seconds", "900",
            "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(GROUP_SEARCH))


def start_sweep() -> None:
    out = FIXED / "g2p2_out"
    pokesim("sweep", *COMMON, "--seeds", str(START_SEEDS), "--group", "2+2", "--no-synergy",
            "--partners", rel(SOLO_SCREEN), "--out", rel(out))
    START_SWEEP.parent.mkdir(parents=True, exist_ok=True)
    (out / "starter_sweep.csv").replace(START_SWEEP)


def start_rank() -> None:
    common = [*COMMON, "--seeds", str(START_SEEDS), "--group", "2+2", "--partners", rel(SOLO_SCREEN)]
    pokesim("rank", *common, "--seed0", "0", "--out", rel(START_RANK))
    for dest, seed0 in START_BLOCKS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        pokesim("rank", *common, "--seed0", seed0, "--out", rel(dest))


BUILD_CHUNK = 4000
BUILD_SCREEN = FIXED / "builds" / "screen_new.csv"
BUILD_REFINE = FIXED / "builds" / "refine_new.csv"


def build_screen() -> None:
    """Melee and ranged builds (build/builds.py): the constrained groups that group_screen.csv lacks, 16 seeds.
    Chunks are written one by one, so an interrupted run resumes where it stopped."""
    keys = builds.missing_screen()
    chunks = FIXED / "builds" / "screen_chunks"
    parts = []
    for i in range(0, len(keys), BUILD_CHUNK):
        n = i // BUILD_CHUNK
        part = chunks / f"{n:03d}.csv"
        parts.append(part)
        if part.exists():
            continue
        only = builds.write_only(chunks / f"{n:03d}.txt", keys[i:i + BUILD_CHUNK])
        pokesim("synergy", "--explicit", "--seeds", str(builds.SCREEN_SEEDS), "--seconds", "900",
                "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(part))
    merge_csv(parts, BUILD_SCREEN)


def build_refine() -> None:
    """The two best groups of each shape and build (build/builds.py), 96 seeds on fresh seeds."""
    short = builds.shortlist(builds.screen_rows())
    only = builds.write_only(FIXED / "builds" / "refine_only.txt", builds.missing_refine(short))
    pokesim("synergy", "--explicit", "--seeds", str(builds.REFINE_SEEDS), "--seed0", str(builds.REFINE_SEED0), "--seconds", "900",
            "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(BUILD_REFINE))


def merge_csv(parts: list[Path], out: Path) -> None:
    lines: list[str] = []
    header = None
    for part in parts:
        text = part.read_text(encoding="utf8").splitlines()
        if header is None:
            header = text[0]
        lines.extend(text[1:])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join([header or "", *lines]) + "\n", encoding="utf8")


STAGES = (
    ("solo_screen", SOLO_SCREEN, solo_screen),
    ("solo_refine", SOLO_REFINE, solo_refine),
    ("solo_contend", SOLO_SWEEP, solo_contend),
    ("group_screen", GROUP_SCREEN, group_screen),
    ("group_refine", GROUP_SEARCH, group_refine),
    ("start_sweep", START_SWEEP, start_sweep),
    ("start_rank", START_RANK, start_rank),
    ("build_screen", BUILD_SCREEN, build_screen),
    ("build_refine", BUILD_REFINE, build_refine),
)


def run_sim(first: str | None, force: bool) -> None:
    if not BIN.exists():
        subprocess.run(["cargo", "build", "--release", "--manifest-path", str(SIM / "sim-rs" / "Cargo.toml")], check=True)
    names = [name for name, _, _ in STAGES]
    if first is not None and first not in names:
        raise SystemExit(f"unknown stage {first}; stages are {', '.join(names)}")
    started = first is None
    for name, output, fn in STAGES:
        started = started or name == first
        if started and (force or first is not None or not output.exists()):
            print(f"== {name}", flush=True)
            fn()
        else:
            print(f"== {name}: skipped ({output.name} exists)", flush=True)


def rebuild(out: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "build" / "make_definitive.py"),
            "--rank-200",
            str(START_RANK),
            "--sweep",
            str(START_SWEEP),
            "--best-sweep",
            str(SOLO_SWEEP),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        check=True,
    )


def facts() -> None:
    subprocess.run([sys.executable, str(ROOT / "build" / "facts_export.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "build" / "refresh_summaries.py")], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the ranking from the engine.")
    parser.add_argument("--check", action="store_true", help="Fail if a rebuild differs from the committed CSV.")
    parser.add_argument("--sim", action="store_true", help="Rerun the engine stages first.")
    parser.add_argument("--from", dest="first", default=None, help="With --sim: rerun this stage and the ones after it.")
    parser.add_argument("--force", action="store_true", help="With --sim: rerun stages whose output exists.")
    parser.add_argument("--facts", action="store_true", help="Rewrite facts.parquet and the summaries that no longer match.")
    args = parser.parse_args()

    if args.sim:
        run_sim(args.first, args.force)

    ranking = ROOT / "data" / "ranking_definitive.csv"
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ranking.csv"
            rebuild(out)
            if not filecmp.cmp(out, ranking, shallow=False):
                raise SystemExit("ranking_definitive.csv does not match a rebuild from the committed sim CSVs")
        print("ranking matches the committed sim CSVs")
        if builds.main(["--check"]):
            raise SystemExit("data/builds.csv: una fila no cumple las reglas de build")
        return

    rebuild(ranking)
    print(f"wrote {ranking}")
    if builds.main([]):
        raise SystemExit("data/builds.csv: una fila no cumple las reglas de build")
    if args.facts:
        facts()


if __name__ == "__main__":
    main()
