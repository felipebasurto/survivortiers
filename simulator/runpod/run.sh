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
    FUNNEL_OUT="$TASK_SIM_DIR/runpod-funnel/$FUNNEL_PRESET"
    mkdir -p -- "$FUNNEL_OUT"
    "$TASK_BINARY" funnel plan "$FUNNEL_MANIFEST" "$FUNNEL_OUT/plan.json" > "$FUNNEL_OUT/plan-counts.json"
    python3 - "$FUNNEL_OUT/plan.json" "$TASK_SCRIPT_DIR/vm-rate.json" "$FUNNEL_DRY" <<'PY'
import json, os, sys
plan, rate, dry = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3] == "1"
samples = sorted(float(x) for x in rate["matchesPerSecond"])
median = samples[len(samples) // 2]
scaled = median / float(rate["threads"]) * float(rate["targetVcpu"])
tasks = int(plan["counts"]["tasksUpperBound"])
hours = tasks / scaled / 3600.0
price = float(os.environ.get("POKESIM_HOURLY_USD", rate["hourlyUsd"]))
budget = float(os.environ.get("POKESIM_BUDGET_USD", rate["maxUsd"]))
cap = min(float(rate["maxUsd"]), budget)
cost = hours * price
print(f"tasksUpperBound {tasks}")
print(f"recallTasksUpper {plan['counts'].get('recallTasksUpper', 0)}")
print(f"measured median {median:.2f} matches/s at {rate['threads']} threads on {rate['hostCores']} cores, {len(samples)} runs, range {samples[0]:.2f}-{samples[-1]:.2f}")
print(f"inferred {rate['targetVcpu']}-vCPU rate {scaled:.2f} matches/s, linear in the measured per-core rate")
print(f"ETA {hours:.3f} h, cost {cost:.2f} USD at {price:.2f} USD/h for a cpu5c-sized 32-vCPU host")
print("The ETA uses the plan upper bound. Later stages run fewer groups than the bound, so the morning job should finish sooner.")
over = hours > float(rate["maxHours"]) or cost > cap
if over:
    print(f"ABORT: ETA or cost exceeds {rate['maxHours']} h or {cap:.2f} USD", file=sys.stderr)
    sys.exit(3)
if dry:
    sys.exit(0)
PY
    if (( FUNNEL_DRY )); then
      printf '%s\n' 'Dry run only. No matches were started.'
      exit 0
    fi
    command -v timeout >/dev/null || { printf '%s\n' 'GNU timeout is required (Ubuntu: coreutils).' >&2; exit 2; }
    if [[ "$FUNNEL_PRESET" == "full" ]]; then
      FUNNEL_THREADS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["limits"]["threads"])' "$FUNNEL_MANIFEST")"
      "$TASK_BINARY" funnel calibrate "$FUNNEL_THREADS" | tee "$FUNNEL_OUT/calibrate.json"
    fi
    FUNNEL_RECALL_OK=1
    if [[ "$FUNNEL_PRESET" == "full" ]]; then
      while IFS= read -r FUNNEL_DEX; do
        [[ -n "$FUNNEL_DEX" ]] || continue
        if ! "$TASK_BINARY" funnel recall "$FUNNEL_DEX" "$FUNNEL_OUT/recall-$FUNNEL_DEX.json" "$FUNNEL_OUT/recall-cache-$FUNNEL_DEX"; then
          FUNNEL_RECALL_OK=0
          printf 'Recall for dex %s failed. Continuing the funnel.\n' "$FUNNEL_DEX" >&2
        fi
      done < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
print("\n".join(str(row.get("dex")) for row in d.get("recall") or []))' "$FUNNEL_OUT/plan.json")
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
    tar -C "$TASK_SIM_DIR/runpod-funnel" -czf "$TASK_SIM_DIR/runpod-funnel/funnel-results.tar.gz" "$FUNNEL_PRESET"
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
