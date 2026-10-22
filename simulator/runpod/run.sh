#!/usr/bin/env bash
# Local/Runpod job wrapper. It never creates a cloud resource.
set -euo pipefail
TASK_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TASK_REPO_DIR="$(cd -- "$TASK_SCRIPT_DIR/../.." && pwd)"
TASK_SIM_DIR="$TASK_REPO_DIR/simulator"
TASK_BINARY="$TASK_SIM_DIR/sim-rs/target/release/pokesim"
TASK_ACTION="${1:-help}"
if (( $# )); then shift; fi
cd -- "$TASK_SIM_DIR"

cost_limit() {
  # Production run and resume keep the 7200s default. funnel exports a wall from
  # vm-rate.json maxHours before it calls this, so that default is not the funnel cap.
  local task_rate="${POKESIM_HOURLY_USD:-1.12}"
  local task_budget="${POKESIM_BUDGET_USD:-4.00}"
  local task_wall="${POKESIM_MAX_WALL_SECONDS:-7200}"
  for task_number in "$task_rate" "$task_budget" "$task_wall"; do
    [[ "$task_number" =~ ^[0-9]+([.][0-9]+)?$ ]] || { printf '%s\n' 'Budget, price and duration must be positive numbers.' >&2; return 2; }
  done
  awk -v rate="$task_rate" -v budget="$task_budget" -v wall="$task_wall" 'BEGIN {
    if(rate<=0 || budget<=0 || wall<1) exit 2;
    cap=int(budget/rate*3600)-300;
    if(cap<1) exit 2;
    if(cap>wall) cap=int(wall);
    print cap;
  }'
}

case "$TASK_ACTION" in
  prepare)
    command -v cargo >/dev/null || { printf '%s\n' 'Install Rust (rustup) and a C linker first; see simulator/runpod/README.md.' >&2; exit 2; }
    cargo test --locked --release --manifest-path sim-rs/Cargo.toml
    cargo build --locked --release --manifest-path sim-rs/Cargo.toml --bin pokesim
    "$TASK_BINARY" fingerprint
    ;;
  plan)
    "$TASK_BINARY" production plan "${1:-$TASK_SCRIPT_DIR/production.json}" "${2:-$TASK_SIM_DIR/runpod-plan.json}"
    ;;
  benchmark)
    "$TASK_BINARY" production benchmark "$@"
    ;;
  cost)
    TASK_CAP="$(cost_limit)"
    printf 'Max execution wall time: %s seconds\n' "$TASK_CAP"
    printf 'Quoted machine rate: %s USD/hour; configured compute budget: %s USD\n' "${POKESIM_HOURLY_USD:-1.12}" "${POKESIM_BUDGET_USD:-4.00}"
    printf '%s\n' 'This wrapper does not include pod setup, storage or currency conversion, and does not stop the rented pod.'
    ;;
  funnel)
    FUNNEL_PRESET="${1:-}"
    if (($#)); then shift; fi
    FUNNEL_DRY=0
    if [[ "${1:-}" == "--dry-run" ]]; then
      FUNNEL_DRY=1
    fi
    case "$FUNNEL_PRESET" in
      smoke) FUNNEL_MANIFEST="$TASK_SCRIPT_DIR/funnel-smoke.json" ;;
      full) FUNNEL_MANIFEST="$TASK_SCRIPT_DIR/funnel-full.json" ;;
      *)
        printf '%s\n' 'Usage: bash simulator/runpod/run.sh funnel smoke|full [--dry-run]' >&2
        exit 2
        ;;
    esac
    command -v python3 >/dev/null || { printf '%s\n' 'python3 is required.' >&2; exit 2; }
    if [[ ! -x "$TASK_BINARY" ]]; then
      printf '%s\n' 'Run prepare first so simulator/sim-rs/target/release/pokesim exists.' >&2
      exit 2
    fi
    if [[ -z "${POKESIM_HOURLY_USD:-}" ]]; then
      export POKESIM_HOURLY_USD="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hourlyUsd"])' "$TASK_SCRIPT_DIR/vm-rate.json")"
    fi
    if [[ -z "${POKESIM_BUDGET_USD:-}" ]]; then
      export POKESIM_BUDGET_USD="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["maxUsd"])' "$TASK_SCRIPT_DIR/vm-rate.json")"
    fi
    if [[ -z "${POKESIM_MAX_WALL_SECONDS:-}" ]]; then
      export POKESIM_MAX_WALL_SECONDS="$(python3 -c 'import json,sys; print(int(float(json.load(open(sys.argv[1]))["maxHours"]) * 3600))' "$TASK_SCRIPT_DIR/vm-rate.json")"
    fi
    FUNNEL_OUT="$TASK_SIM_DIR/runpod-funnel/$FUNNEL_PRESET"
    mkdir -p -- "$FUNNEL_OUT"
    "$TASK_BINARY" funnel plan "$FUNNEL_MANIFEST" "$FUNNEL_OUT/plan.json" > "$FUNNEL_OUT/plan-counts.json"
    export FUNNEL_WRAPPER_PATH="$FUNNEL_OUT/wrapper-seconds"
    python3 - "$FUNNEL_OUT/plan-counts.json" "$TASK_SCRIPT_DIR/vm-rate.json" "$FUNNEL_DRY" <<'PY'
import json, os, re, sys
counts, rate, dry = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3] == "1"
samples = sorted(float(x) for x in rate["matchesPerSecond"])
median = samples[len(samples) // 2]
scaled = median / float(rate["threads"]) * float(rate["targetVcpu"])
tasks = int(counts["tasksUpperBound"])
hours = tasks / scaled / 3600.0
price = float(os.environ.get("POKESIM_HOURLY_USD", rate["hourlyUsd"]))
budget = float(os.environ.get("POKESIM_BUDGET_USD", rate["maxUsd"]))
money_cap = min(float(rate["maxUsd"]), budget)
cost = hours * price
wall_text = os.environ.get("POKESIM_MAX_WALL_SECONDS", "")
if wall_text and re.fullmatch(r"[0-9]+(?:[.][0-9]+)?", wall_text) is None:
    print("ABORT: wall must be a plain positive number", file=sys.stderr)
    sys.exit(2)
wall = float(wall_text) if wall_text else float(rate["maxHours"]) * 3600
dollar = int(budget / price * 3600) - 300
if dollar < 1 or wall < 1:
    print("ABORT: budget, price, or wall leaves no wrapper time", file=sys.stderr)
    sys.exit(2)
wrapper = dollar if dollar <= wall else int(wall)
match_s = tasks / scaled
free_inodes = os.statvfs(".").f_favail
print(f"tasksUpperBound {tasks}")
print(f"recallTasksUpper {counts.get('recallTasksUpper', 0)}")
if "fullGroupCap" in counts:
    print(f"fullGroupCap {counts['fullGroupCap']} strataFull {counts.get('strataFull', 0)} strataBeam {counts.get('strataBeam', 0)}")
print(f"measured median {median:.2f} matches/s at {rate['threads']} threads on {rate['hostCores']} cores, {len(samples)} runs, range {samples[0]:.2f}-{samples[-1]:.2f}")
print(f"inferred {rate['targetVcpu']}-vCPU rate {scaled:.2f} matches/s, linear in the measured per-core rate")
print(f"ETA {hours:.3f} h, cost {cost:.2f} USD at {price:.2f} USD/h for a cpu5c-sized 32-vCPU host")
print(f"wrapper wall {wrapper} s after recall, match time {match_s:.0f} s")
print(f"free inodes {free_inodes}, checkpoint files {tasks}")
print("The ETA is match time for the plan upper bound. The wrapper clock starts after recall. Checkpoint index reads sit inside the wrapper and are not in the ETA.")
over = hours > float(rate["maxHours"]) or cost > money_cap or match_s > wrapper
if over:
    print(
        f"ABORT: ETA or cost exceeds {rate['maxHours']} h or {money_cap:.2f} USD, or match time exceeds the wrapper wall of {wrapper} s",
        file=sys.stderr,
    )
    sys.exit(3)
open(os.environ["FUNNEL_WRAPPER_PATH"], "w").write(f"{wrapper}\n")
if dry:
    sys.exit(0)
PY
    if (( FUNNEL_DRY )); then
      printf '%s\n' 'Dry run only. No matches were started.'
      exit 0
    fi
    command -v timeout >/dev/null || { printf '%s\n' 'GNU timeout is required (Ubuntu: coreutils).' >&2; exit 2; }
    if [[ "$FUNNEL_PRESET" == "full" ]]; then
      python3 - "$FUNNEL_OUT/plan-counts.json" <<'PY'
import json, os, sys
tasks = int(json.load(open(sys.argv[1]))["tasksUpperBound"])
st = os.statvfs(".")
free, reported = st.f_favail, st.f_files
print(f"free inodes {free}, inode counter {reported}, checkpoint files {tasks}")
if reported > 0 and free < tasks:
    print(f"ABORT: {free} free inodes is below {tasks} checkpoint files.", file=sys.stderr)
    sys.exit(3)
if reported == 0:
    print("filesystem reported no inode counter. The inode gate did not stop the run.")
PY
      FUNNEL_THREADS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["limits"]["threads"])' "$FUNNEL_MANIFEST")"
      "$TASK_BINARY" funnel calibrate "$FUNNEL_THREADS" | tee "$FUNNEL_OUT/calibrate.json"
      python3 - "$FUNNEL_OUT/calibrate.json" "$FUNNEL_OUT/plan-counts.json" "$FUNNEL_OUT/wrapper-seconds" <<'PY'
import json, sys
cal = json.load(open(sys.argv[1]))
counts = json.load(open(sys.argv[2]))
wrapper = int(float(open(sys.argv[3]).read()))
rate = float(cal["matchesPerSecond"])
threads = max(1, int(cal["threads"]))
samples = max(1, int(cal["tasks"]))
waves = (samples + threads - 1) // threads
steady = rate * waves / (samples / threads)
tasks = int(counts["tasksUpperBound"])
need = tasks / wrapper
print(
    f"calibrate {rate:.2f} matches/s over {samples} tasks on {threads} threads "
    f"({waves} waves). Full-wave equivalent {steady:.2f}. The upper bound needs {need:.2f}."
)
if steady < need:
    print(
        f"ABORT: full-wave equivalent {steady:.2f} matches/s is under {need:.2f}. The upper bound misses the wrapper wall.",
        file=sys.stderr,
    )
    sys.exit(3)
PY
    fi
    FUNNEL_RECALL_OK=1
    if [[ "$FUNNEL_PRESET" == "full" ]]; then
      while IFS= read -r FUNNEL_DEX; do
        [[ -n "$FUNNEL_DEX" ]] || continue
        if ! "$TASK_BINARY" funnel recall "$FUNNEL_DEX" "$FUNNEL_OUT/recall-$FUNNEL_DEX.json" "$FUNNEL_OUT/recall-cache-$FUNNEL_DEX"; then
          FUNNEL_RECALL_OK=0
          printf 'Recall for dex %s failed. Continuing the funnel.\n' "$FUNNEL_DEX" >&2
        fi
      done < <(python3 - "$FUNNEL_OUT/plan.json" <<'PY'
import json, sys
needle = b',"recall":'
with open(sys.argv[1], "rb") as handle:
    window = b""
    while True:
        chunk = handle.read(1 << 20)
        if not chunk:
            raise SystemExit("recall list missing from plan")
        window += chunk
        at = window.find(needle)
        if at < 0:
            window = window[-(len(needle) - 1):]
            continue
        buf = window[at + len(needle):]
        decoder = json.JSONDecoder()
        while True:
            try:
                rows, _ = decoder.raw_decode(buf.decode())
                break
            except json.JSONDecodeError:
                more = handle.read(1 << 20)
                if not more:
                    raise
                buf += more
        break
for row in rows:
    print(row.get("dex"))
PY
)
      python3 - "$FUNNEL_OUT" "$FUNNEL_RECALL_OK" <<'PY'
import json, pathlib, sys
out, ok = pathlib.Path(sys.argv[1]), sys.argv[2] == "1"
rows = []
for path in sorted(out.glob("recall-*.json")):
    doc = json.loads(path.read_text())
    ok = ok and doc.get("ok") is True
    rows.extend(doc.get("rows") or [])
(out / "recall.json").write_text(json.dumps({"ok": ok and bool(rows), "rows": rows}) + "\n")
PY
    fi
    TASK_CAP="$(cost_limit)"
    TASK_STARTED="$SECONDS"
    FUNNEL_ACTION="run"
    while true; do
      TASK_LEFT="$((TASK_CAP - (SECONDS - TASK_STARTED)))"
      if (( TASK_LEFT < 60 )); then
        printf '%s\n' 'Compute budget reached with funnel tasks still unfinished. Keep the cache and resume later. Then terminate the pod. This script does not stop billing.' >&2
        exit 75
      fi
      printf 'Funnel %s, about %s seconds left in the wrapper budget.\n' "$FUNNEL_ACTION" "$TASK_LEFT" >&2
      set +e
      timeout --foreground --signal=TERM --kill-after=30s "${TASK_LEFT}s" \
        "$TASK_BINARY" funnel "$FUNNEL_ACTION" "$FUNNEL_OUT/plan.json" "$FUNNEL_OUT/cache" "$FUNNEL_OUT/results.json"
      TASK_STATUS="$?"
      set -e
      if (( TASK_STATUS == 124 || TASK_STATUS == 137 )); then
        printf '%s\n' 'Outer deadline hit. Keep the cache and resume later. Then terminate the pod.' >&2
        exit 75
      fi
      if (( TASK_STATUS != 0 )); then
        exit "$TASK_STATUS"
      fi
      FUNNEL_MISSING="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(0 if d.get("complete") else 1)' "$FUNNEL_OUT/results.json")"
      if [[ "$FUNNEL_MISSING" == 0 ]]; then
        break
      fi
      printf 'Funnel invocation stopped with work remaining (completed %s). Resuming.\n' "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("completedTasks"))' "$FUNNEL_OUT/results.json")" >&2
      FUNNEL_ACTION="resume"
    done
    FUNNEL_REPORT_ARGS=("$FUNNEL_OUT/results.json" "$FUNNEL_OUT/report.md")
    if [[ -f "$FUNNEL_OUT/recall.json" ]]; then
      FUNNEL_REPORT_ARGS+=("$FUNNEL_OUT/recall.json")
    fi
    "$TASK_BINARY" funnel report "${FUNNEL_REPORT_ARGS[@]}"
    PYTHONPATH="$TASK_REPO_DIR" python3 "$TASK_REPO_DIR/build/funnel_export.py" "$FUNNEL_OUT/results.json" "$FUNNEL_OUT/web.json"
    tar -C "$TASK_SIM_DIR/runpod-funnel" -czf "$TASK_SIM_DIR/runpod-funnel/funnel-results.tar.gz" \
      --exclude="$FUNNEL_PRESET/cache" \
      --exclude="$FUNNEL_PRESET/plan.json" \
      --exclude="$FUNNEL_PRESET/recall-cache-*" \
      "$FUNNEL_PRESET"
    printf '%s\n' "Funnel $FUNNEL_PRESET finished. Archive: simulator/runpod-funnel/funnel-results.tar.gz. Terminate the pod yourself. This script does not stop billing."
    ;;
  run|resume)
    command -v timeout >/dev/null || { printf '%s\n' 'GNU timeout is required (Ubuntu: coreutils).' >&2; exit 2; }
    command -v python3 >/dev/null || { printf '%s\n' 'python3 is required to read missingTasks.' >&2; exit 2; }
    TASK_CAP="$(cost_limit)"
    TASK_PLAN="${1:-$TASK_SIM_DIR/runpod-plan.json}"
    TASK_CACHE="${2:-$TASK_SIM_DIR/runpod-cache}"
    TASK_RESULTS="${3:-$TASK_SIM_DIR/runpod-results.json}"
    TASK_STARTED="$SECONDS"
    printf 'Execution deadline: %s seconds at %s USD/hour.\n' "$TASK_CAP" "${POKESIM_HOURLY_USD:-1.12}" >&2
    printf '%s\n' 'Each invocation stops itself after the plan wall limit and this wrapper resumes it until the ledger is done or the budget ends.' >&2
    while true; do
      TASK_LEFT="$((TASK_CAP - (SECONDS - TASK_STARTED)))"
      if (( TASK_LEFT < 60 )); then
        printf '%s\n' 'Compute budget reached with tasks still unfinished. Keep the cache and resume later. Then terminate the pod; this script does not stop billing.' >&2
        exit 75
      fi
      set +e
      timeout --foreground --signal=TERM --kill-after=30s "${TASK_LEFT}s" \
        "$TASK_BINARY" production "$TASK_ACTION" "$TASK_PLAN" "$TASK_CACHE" "$TASK_RESULTS"
      TASK_STATUS="$?"
      set -e
      if (( TASK_STATUS == 124 || TASK_STATUS == 137 )); then
        printf '%s\n' 'Outer deadline hit. Keep the cache and resume later. Then terminate the pod.' >&2
        exit 75
      fi
      if (( TASK_STATUS != 0 )); then
        exit "$TASK_STATUS"
      fi
      TASK_MISSING="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("missingTasks") or []))' "$TASK_RESULTS")"
      if [[ "$TASK_MISSING" == 0 ]]; then
        printf '%s\n' 'Production ledger finished. Copy the results, then terminate the pod. This script does not stop billing.' >&2
        exit 0
      fi
      printf 'Invocation stopped with %s tasks remaining; resuming.\n' "$TASK_MISSING" >&2
      TASK_ACTION="resume"
    done
    ;;
  *)
    printf '%s\n' \
      'Usage: bash simulator/runpod/run.sh prepare|plan|benchmark|cost|run|resume|funnel' \
      'prepare: compile and test only; plan: write a finite ledger without matches.' \
      'benchmark: bounded mature scenes only; run/resume: explicit production execution.' \
      'funnel smoke|full [--dry-run]: staged search. full --dry-run prints the ETA and does not simulate.' \
      'Cloud compute is not released automatically: save results, then terminate your pod.'
    ;;
esac
