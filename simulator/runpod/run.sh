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
      'Usage: bash simulator/runpod/run.sh prepare|plan|benchmark|cost|run|resume' \
      'prepare: compile and test only; plan: write a finite ledger without matches.' \
      'benchmark: bounded mature scenes only; run/resume: explicit production execution.' \
      'Cloud compute is not released automatically: save results, then terminate your pod.'
    ;;
esac
