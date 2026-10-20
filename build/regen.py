"""Regenerate every published input from the engine, in one resumable run.

    python3 build/regen.py --sim        # run every simulation stage, then write MANIFEST.json
    python3 build/regen.py              # publish: rebuild data/ from the stage outputs
    python3 build/regen.py --check      # fail if data/ differs from a rebuild of the committed CSVs
    python3 build/regen.py --facts      # facts.parquet and the summaries, after a publish

A stage whose output exists is skipped, so an interrupted run resumes where it stopped. The group
screen runs in chunks of GROUP_CHUNK groups, each written to a temporary file and renamed when done.
`--from STAGE` reruns that stage and the ones after it; `--force` reruns stages whose output exists.

One path for every simulated group: `pokesim synergy --explicit` runs the groups named in a file.
The group_gate stage proves on a sample that the generator and the explicit path give the same bytes,
and stops the run if they do not.

Smoke tests never publish. Point SURVIVOR_FIXED at a scratch folder and shrink the run:

    SURVIVOR_FIXED=/tmp/smoke/fixed python3 build/regen.py --sim --quick 16 --scope 1,94,25

`--quick N` divides every seed count by N. `--scope` keeps the listed species in the group, build,
counterfactual and passive stages. Publishing refuses to run on a folder other than the default.

The order matters: the group search ranks partners from the solo sweep.

1. solo screen    every simulated pool move as a start, 16 seeds (partners for the rest)
2. solo refine    each species' best 3 attacks on fresh seeds
3. solo contend   the best 2 attacks of the top species again on many more seeds, merged into the solo sweep
4. group gate     300 sampled groups, generator and explicit path, byte-compared
5. group screen   every searched group, 16 seeds, in chunks
6. group refine   the best 2 groups of each shape (picks.shape_of) on fresh seeds
7. start sweep    every pool move as the start of a 2+2 group, 16 seeds (Repertorio opening)
8. start rank     the game's start move, 16 seeds, three disjoint blocks
9. build screen   the constrained build groups the group screen does not hold, 16 seeds
10. build refine  the two best groups of each shape and build, 96 seeds
11. rank          the ranking, from the stage outputs (make_definitive.py)
12. counterfactuals  per-species counterfactuals behind the ficha summaries (counterfactual_bench.py)
13. passive coins    card-priority runs for the passives page (card_priority.py)

Not regenerated here: the 150-species passive table (simulator/pasivas_rank.py reads items_g2p2.csv,
which is not in the repo; the species list has to be decided first).

pokedex_export.json and game_stats.json are extracts of the game
(`build/import_game_combat.py`, `build/export_game_stats.js`, both read the game repo at
`legal.GAME_COMMIT`). move_tierlist_v4.csv is the analysis table; the rank does not read it.
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds  # noqa: E402
import picks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator"
BIN = SIM / "sim-rs" / "target" / "release" / "pokesim"
PUBLISHED = SIM / "results" / "fixed_group"
FIXED = Path(os.environ["SURVIVOR_FIXED"]) if os.environ.get("SURVIVOR_FIXED") else PUBLISHED

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
COUNTERFACTUAL_SEEDS = 200
COIN_SEEDS = 100
GATE_SAMPLE = 300
GROUP_CHUNK = 25_000
BUILD_CHUNK = 4_000
COMMON = ["--seconds", "900", "--status", "--terrain", "--xkinds"]

SOLO_SCREEN = FIXED / "solo_screen.csv"
SOLO_REFINE = FIXED / "solo_refine.csv"
SOLO_CONTEND = FIXED / "solo_contend.csv"
SOLO_SWEEP = FIXED / "solo_sweep.csv"
GATE_RESULT = FIXED / "gate" / "result.json"
GROUP_SCREEN = FIXED / "group_screen.csv"
GROUP_SEARCH = FIXED / "group_search.csv"
START_SWEEP = FIXED / "g2p2" / "starter_sweep.csv"
START_RANK = FIXED / "g2p2" / "rank_200.csv"
START_BLOCKS = ((FIXED / "stage2" / "rank_b.csv", "100"), (FIXED / "stage2" / "rank_c.csv", "200"))
BUILD_SCREEN = FIXED / "builds" / "screen_new.csv"
BUILD_REFINE = FIXED / "builds" / "refine_new.csv"
RANKING = FIXED / "ranking_definitive.csv"
COUNTERFACTUAL_G2P2 = FIXED / "counterfactuals_g2p2.csv"
COUNTERFACTUAL_SOLO = FIXED / "counterfactuals_solo.csv"
PASSIVE_COINS = FIXED / "passives_coins_g2p2.csv"
PASSIVE_JSON = FIXED / "passive_sim.json"
MANIFEST = FIXED / "MANIFEST.json"

SEED_DIV = 1
SCOPE: set[int] | None = None
RUN: dict = {}


def seeds(base: int) -> int:
    return max(1, base // SEED_DIV)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(SIM))
    except ValueError:
        return str(path)


def pokesim(*args: str) -> None:
    subprocess.run([str(BIN), *args], cwd=SIM, check=True)


def in_scope(dex: int) -> bool:
    return SCOPE is None or dex in SCOPE


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


def data_rows(path: Path) -> int:
    with path.open(encoding="utf8") as f:
        return sum(1 for line in f if line.strip() and not line.startswith("#")) - 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---- solo stages -----------------------------------------------------------------------------

def solo_screen() -> None:
    out = FIXED / "solo_screen_out"
    pokesim("sweep", *COMMON, "--seeds", str(seeds(SCREEN_SEEDS)), "--no-synergy", "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_SCREEN)
    shutil.rmtree(out, ignore_errors=True)


def solo_refine() -> None:
    short = picks.shortlist_moves(picks.load_rows(SOLO_SCREEN), SOLO_REFINE_TOP)
    only = write_only(FIXED / "solo_refine_only.txt", [f"{d}|{r['start']}" for d, rows in short.items() for r in rows])
    out = FIXED / "solo_refine_out"
    pokesim("sweep", *COMMON, "--seeds", str(seeds(SOLO_REFINE_SEEDS)), "--seed0", str(SOLO_SEED0), "--no-synergy",
            "--only", rel(only), "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_REFINE)
    shutil.rmtree(out, ignore_errors=True)


def contenders() -> dict[int, list[dict]]:
    best = picks.best_moves(picks.load_rows(SOLO_REFINE))
    top = sorted(best.values(), key=lambda r: picks.move_order(r))[:CONTEND_SPECIES]
    by_dex = picks.shortlist_moves(picks.load_rows(SOLO_REFINE), CONTEND_MOVES)
    return {int(r["dex"]): by_dex[int(r["dex"])] for r in top}


def solo_contend() -> None:
    chosen = contenders()
    only = write_only(FIXED / "solo_contend_only.txt", [f"{d}|{r['start']}" for d, rows in chosen.items() for r in rows])
    out = FIXED / "solo_contend_out"
    pokesim("sweep", *COMMON, "--seeds", str(seeds(CONTEND_SEEDS)), "--seed0", str(CONTEND_SEED0), "--no-synergy",
            "--only", rel(only), "--out", rel(out))
    (out / "starter_sweep.csv").replace(SOLO_CONTEND)
    shutil.rmtree(out, ignore_errors=True)
    merge_solo(set(chosen))


def merge_solo(contend: set[int]) -> None:
    """The solo sweep: the refine rows, with the contenders' rows replaced by the many-seed rows of
    their best moves. A species never mixes seed counts."""
    refine = picks.load_rows(SOLO_REFINE)
    contend_rows = picks.load_rows(SOLO_CONTEND)
    rows = [r for r in refine if int(r["dex"]) not in contend] + contend_rows
    rows.sort(key=lambda r: (int(r["dex"]), r["start"]))
    write_rows(SOLO_SWEEP, header_of(SOLO_CONTEND), rows)


# ---- group stages: one path (--explicit) ---------------------------------------------------

def group_keys() -> list[str]:
    """Every group the generator searches, as dex|group. Listing runs no game."""
    out = subprocess.run([str(BIN), "synergy", "--list", "--partners", rel(SOLO_SCREEN)], cwd=SIM,
                         check=True, capture_output=True, text=True).stdout
    keys = [line.strip() for line in out.splitlines() if "|" in line]
    return [k for k in keys if in_scope(int(k.split("|", 1)[0]))]


def group_gate() -> None:
    """Generator and explicit path must give the same bytes on a sample, or the run stops."""
    keys = group_keys()
    step = max(1, len(keys) // GATE_SAMPLE)
    sample = keys[::step][:GATE_SAMPLE]
    gate = FIXED / "gate"
    only = write_only(gate / "sample.txt", sample)
    generator, explicit = gate / "generator.csv", gate / "explicit.csv"
    common = ["--seeds", str(seeds(SCREEN_SEEDS)), "--seconds", "900", "--partners", rel(SOLO_SCREEN),
              "--only", rel(only)]
    pokesim("synergy", *common, "--out", rel(generator))
    pokesim("synergy", "--explicit", *common, "--out", rel(explicit))
    a = sorted(generator.read_text(encoding="utf8").splitlines())
    b = sorted(explicit.read_text(encoding="utf8").splitlines())
    differ = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
    if differ:
        raise SystemExit(f"group gate: the explicit path differs from the generator in {differ} lines; see {gate}")
    GATE_RESULT.parent.mkdir(parents=True, exist_ok=True)
    GATE_RESULT.write_text(json.dumps({"sample": len(sample), "groups": len(keys), "identical": True}, indent=1) + "\n",
                           encoding="utf8")


def group_screen() -> None:
    keys = group_keys()
    parts: list[Path] = []
    for n, i in enumerate(range(0, len(keys), GROUP_CHUNK)):
        part = FIXED / "group_screen_parts" / f"{n:03d}.csv"
        parts.append(part)
        if part.exists():
            continue
        only = write_only(part.with_suffix(".txt"), keys[i:i + GROUP_CHUNK])
        tmp = part.with_suffix(".tmp")
        pokesim("synergy", "--explicit", "--seeds", str(seeds(SCREEN_SEEDS)), "--seconds", "900",
                "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(tmp))
        tmp.replace(part)
    merged = merge_csv(parts, GROUP_SCREEN)
    if merged != len(keys):
        raise SystemExit(f"group screen: {merged} rows for {len(keys)} groups")


def group_refine() -> None:
    short = picks.shortlist_groups(picks.load_rows(GROUP_SCREEN), GROUP_REFINE_PER_SHAPE)
    only = write_only(FIXED / "group_refine_only.txt", [f"{d}|{r['group']}" for d, rows in short.items() for r in rows])
    pokesim("synergy", "--explicit", "--seeds", str(seeds(GROUP_REFINE_SEEDS)), "--seed0", str(GROUP_SEED0),
            "--seconds", "900", "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(GROUP_SEARCH))


def start_sweep() -> None:
    out = FIXED / "g2p2_out"
    pokesim("sweep", *COMMON, "--seeds", str(seeds(START_SEEDS)), "--group", "2+2", "--no-synergy",
            "--partners", rel(SOLO_SCREEN), "--out", rel(out))
    START_SWEEP.parent.mkdir(parents=True, exist_ok=True)
    (out / "starter_sweep.csv").replace(START_SWEEP)
    shutil.rmtree(out, ignore_errors=True)


def start_rank() -> None:
    common = [*COMMON, "--seeds", str(seeds(START_SEEDS)), "--group", "2+2", "--partners", rel(SOLO_SCREEN)]
    pokesim("rank", *common, "--seed0", "0", "--out", rel(START_RANK))
    for dest, seed0 in START_BLOCKS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        pokesim("rank", *common, "--seed0", seed0, "--out", rel(dest))


def build_screen() -> None:
    """Melee and ranged builds (build/builds.py): the constrained groups the group screen does not hold.
    Chunks are written one by one, so an interrupted run resumes where it stopped."""
    keys = [k for k in builds.missing_screen() if in_scope(k[0])]
    chunks = FIXED / "builds" / "screen_chunks"
    parts: list[Path] = []
    for n, i in enumerate(range(0, len(keys), BUILD_CHUNK)):
        part = chunks / f"{n:03d}.csv"
        parts.append(part)
        if part.exists():
            continue
        only = builds.write_only(chunks / f"{n:03d}.txt", keys[i:i + BUILD_CHUNK])
        tmp = part.with_suffix(".tmp")
        pokesim("synergy", "--explicit", "--seeds", str(seeds(builds.SCREEN_SEEDS)), "--seconds", "900",
                "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(tmp))
        tmp.replace(part)
    merge_csv(parts, BUILD_SCREEN)


def build_refine() -> None:
    """The two best groups of each shape and build (build/builds.py), 96 seeds on fresh seeds."""
    short = builds.shortlist(builds.screen_rows())
    only = builds.write_only(FIXED / "builds" / "refine_only.txt", builds.missing_refine(short))
    pokesim("synergy", "--explicit", "--seeds", str(seeds(builds.REFINE_SEEDS)), "--seed0", str(builds.REFINE_SEED0),
            "--seconds", "900", "--partners", rel(SOLO_SCREEN), "--only", rel(only), "--out", rel(BUILD_REFINE))


def merge_csv(parts: list[Path], out: Path) -> int:
    lines: list[str] = []
    header = None
    for part in parts:
        text = part.read_text(encoding="utf8").splitlines()
        if header is None:
            header = text[0]
        lines.extend(text[1:])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join([header or "", *lines]) + "\n", encoding="utf8")
    return len(lines)


# ---- ranking, counterfactuals and passives ----------------------------------------------------

def rank() -> None:
    """make_definitive.py on the stage outputs, into FIXED (publishing copies it to data/)."""
    rebuild(RANKING)


def counterfactuals() -> None:
    """Task lists from counterfactual_bench.py, run by pokesim tasks. Reads the ranking from FIXED."""
    env = {**os.environ, "SURVIVOR_RANKING": str(RANKING)}
    cf = FIXED / "counterfactuals"
    cf.mkdir(parents=True, exist_ok=True)
    for name, flags, out in (
        ("g2p2", ["--group", "2+2", "--terrain", "--status", "--partners", rel(SOLO_SWEEP)], COUNTERFACTUAL_G2P2),
        ("solo", ["--terrain", "--status", "--xkinds"], COUNTERFACTUAL_SOLO),
    ):
        args = [sys.executable, str(SIM / "counterfactual_bench.py")] + ([] if name == "g2p2" else ["--solo-best"])
        text = subprocess.run(args, cwd=SIM, check=True, capture_output=True, text=True, env=env).stdout
        tasks = cf / f"{name}_tasks.txt"
        tasks.write_text("".join(line + "\n" for line in text.splitlines() if line_in_scope(line)), encoding="utf8")
        tmp = out.with_suffix(".tmp")
        pokesim("tasks", rel(tasks), *flags, "--seeds", str(seeds(COUNTERFACTUAL_SEEDS)), "--out", rel(tmp))
        tmp.replace(out)


def line_in_scope(line: str) -> bool:
    head = line.split(",", 1)[0].strip()
    return not head.isdigit() or in_scope(int(head))


def passive_coins() -> None:
    """Card-priority runs (card_priority.py tasks), then the order that the passives page reads."""
    tasks = FIXED / "passives" / "coin_tasks.txt"
    tasks.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(SIM / "card_priority.py"), "tasks", str(tasks)], cwd=SIM, check=True)
    lines = [line for line in tasks.read_text(encoding="utf8").splitlines() if line_in_scope(line)]
    tasks.write_text("".join(line + "\n" for line in lines), encoding="utf8")
    tmp = PASSIVE_COINS.with_suffix(".tmp")
    pokesim("tasks", rel(tasks), "--group", "2+2", "--terrain", "--status", "--full-cards", "--heal-below", "0.70",
            "--partners", rel(SOLO_SWEEP), "--seeds", str(seeds(COIN_SEEDS)), "--out", rel(tmp))
    tmp.replace(PASSIVE_COINS)
    if SCOPE:
        print("   passive order skipped: it needs all 966 species, and --scope is set", flush=True)
        return
    subprocess.run([sys.executable, str(SIM / "card_priority.py"), "order", str(PASSIVE_COINS), str(PASSIVE_JSON)],
                   cwd=SIM, check=True)


# ---- stage table, manifest and run -----------------------------------------------------------

STAGES = (
    ("solo_screen", SOLO_SCREEN, solo_screen),
    ("solo_refine", SOLO_REFINE, solo_refine),
    ("solo_contend", SOLO_SWEEP, solo_contend),
    ("group_gate", GATE_RESULT, group_gate),
    ("group_screen", GROUP_SCREEN, group_screen),
    ("group_refine", GROUP_SEARCH, group_refine),
    ("start_sweep", START_SWEEP, start_sweep),
    ("start_rank", START_RANK, start_rank),
    ("build_screen", BUILD_SCREEN, build_screen),
    ("build_refine", BUILD_REFINE, build_refine),
    ("rank", RANKING, rank),
    ("counterfactuals", COUNTERFACTUAL_G2P2, counterfactuals),
    ("passive_coins", PASSIVE_JSON, passive_coins),
)


def git_state() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def write_manifest(stage_times: dict[str, float], done: list[str]) -> None:
    outputs = {}
    for name, output, _ in STAGES:
        if name in done and output.exists():
            outputs[name] = {"file": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
                             "bytes": output.stat().st_size, "sha256": sha256(output)}
    doc = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "started": RUN["started"],
        "git": git_state(),
        "binary": {"path": rel(BIN), "sha256": sha256(BIN) if BIN.exists() else None},
        "machine": {"cpu": cpu_model(), "logical_cpus": os.cpu_count(), "rayon_threads": os.environ.get("RAYON_NUM_THREADS"),
                    "python": platform.python_version(), "platform": platform.platform()},
        "game_vendor": sorted(p.parent.name for p in (SIM / "vendor").glob("*/COMMIT")),
        "run": {"quick": SEED_DIV, "scope": sorted(SCOPE) if SCOPE else None, "results": str(FIXED)},
        "seeds": {"screen": seeds(SCREEN_SEEDS), "solo_refine": seeds(SOLO_REFINE_SEEDS), "contend": seeds(CONTEND_SEEDS),
                  "group_refine": seeds(GROUP_REFINE_SEEDS), "start": seeds(START_SEEDS),
                  "counterfactuals": seeds(COUNTERFACTUAL_SEEDS), "coins": seeds(COIN_SEEDS),
                  "build_screen": seeds(builds.SCREEN_SEEDS), "build_refine": seeds(builds.REFINE_SEEDS)},
        "stage_seconds": stage_times,
        "stages_done": done,
        "outputs": outputs,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf8")


def run_sim(first: str | None, force: bool) -> None:
    if not BIN.exists():
        subprocess.run(["cargo", "build", "--release", "--manifest-path", str(SIM / "sim-rs" / "Cargo.toml")], check=True)
    names = [name for name, _, _ in STAGES]
    if first is not None and first not in names:
        raise SystemExit(f"unknown stage {first}; stages are {', '.join(names)}")
    real = SEED_DIV == 1 and SCOPE is None
    if real and git_state()["dirty"] and not os.environ.get("ALLOW_DIRTY"):
        raise SystemExit("the git tree has uncommitted changes: commit them first, so MANIFEST.json names the code that ran "
                         "(ALLOW_DIRTY=1 overrides this, and the manifest says dirty)")
    RUN["started"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Timings of earlier invocations stay in the manifest, so a resumed run keeps the whole history.
    stage_times: dict[str, float] = {}
    if MANIFEST.exists():
        stage_times.update(json.loads(MANIFEST.read_text(encoding="utf8")).get("stage_seconds", {}))
    done: list[str] = []
    started = first is None
    for name, output, fn in STAGES:
        started = started or name == first
        if started and (force or first is not None or not output.exists()):
            print(f"== {name}", flush=True)
            t0 = time.perf_counter()
            fn()
            stage_times[name] = round(time.perf_counter() - t0, 1)
            print(f"   {name}: {stage_times[name]} s", flush=True)
        else:
            print(f"== {name}: skipped ({output.name} exists)", flush=True)
        done.append(name)
        write_manifest(stage_times, done)
    print(f"manifest: {MANIFEST}", flush=True)


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


def publish() -> None:
    """Copy the stage outputs that the website reads into data/. Only the published folder can do this."""
    if FIXED != PUBLISHED:
        raise SystemExit(f"publishing reads {PUBLISHED}; SURVIVOR_FIXED points at {FIXED}. Nothing was written.")
    ranking = ROOT / "data" / "ranking_definitive.csv"
    rebuild(ranking)
    print(f"wrote {ranking}")
    if builds.main([]):
        raise SystemExit("data/builds.csv: una fila no cumple las reglas de build")
    if PASSIVE_JSON.exists():
        (ROOT / "data" / "passive_sim.json").write_text(PASSIVE_JSON.read_text(encoding="utf8"), encoding="utf8")


def facts() -> None:
    subprocess.run([sys.executable, str(ROOT / "build" / "facts_export.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "build" / "refresh_summaries.py")], cwd=ROOT, check=True)


def main() -> None:
    global SEED_DIV, SCOPE
    parser = argparse.ArgumentParser(description="Regenerate the published data from the engine.")
    parser.add_argument("--check", action="store_true", help="Fail if a rebuild differs from the committed CSV.")
    parser.add_argument("--sim", action="store_true", help="Run the simulation stages and write MANIFEST.json.")
    parser.add_argument("--from", dest="first", default=None, help="With --sim: rerun this stage and the ones after it.")
    parser.add_argument("--force", action="store_true", help="With --sim: rerun stages whose output exists.")
    parser.add_argument("--quick", type=int, default=1, help="With --sim: divide every seed count by N (smoke tests).")
    parser.add_argument("--scope", default=None, help="With --sim: comma-separated dex numbers to keep in the group, "
                                                     "build, counterfactual and passive stages.")
    parser.add_argument("--facts", action="store_true", help="Rewrite facts.parquet and the summaries that no longer match.")
    args = parser.parse_args()
    SEED_DIV = max(1, args.quick)
    SCOPE = {int(x) for x in args.scope.split(",")} if args.scope else None
    if (SEED_DIV > 1 or SCOPE) and not args.sim:
        raise SystemExit("--quick and --scope only apply to --sim")

    if args.sim:
        run_sim(args.first, args.force)
        print("simulation stages done. Publish with: python3 build/regen.py", flush=True)
        return

    if args.check:
        ranking = ROOT / "data" / "ranking_definitive.csv"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ranking.csv"
            rebuild(out)
            if not filecmp.cmp(out, ranking, shallow=False):
                raise SystemExit("ranking_definitive.csv does not match a rebuild from the committed sim CSVs")
        print("ranking matches the committed sim CSVs")
        if builds.main(["--check"]):
            raise SystemExit("data/builds.csv: una fila no cumple las reglas de build")
        return

    publish()
    if args.facts:
        facts()


if __name__ == "__main__":
    main()
