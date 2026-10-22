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
  ranking)
    RANKING_PRESET="${1:-}"
    if (($#)); then shift; fi
    RANKING_DRY=0
    if [[ "${1:-}" == "--dry-run" ]]; then RANKING_DRY=1; shift; fi
    if (($#)) || [[ "$RANKING_PRESET" != smoke && "$RANKING_PRESET" != full ]]; then
      printf '%s\n' 'Usage: bash simulator/runpod/run.sh ranking smoke|full [--dry-run]' >&2
      exit 2
    fi
    command -v python3 >/dev/null || { printf '%s\n' 'python3 is required.' >&2; exit 2; }
    [[ -x "$TASK_BINARY" ]] || { printf '%s\n' 'Run prepare first so simulator/sim-rs/target/release/pokesim exists.' >&2; exit 2; }
    RANKING_MANIFEST="$TASK_SCRIPT_DIR/ranking-$RANKING_PRESET.json"
    RANKING_OUT="$TASK_SIM_DIR/runpod-ranking/$RANKING_PRESET"
    mkdir -p -- "$RANKING_OUT"
    RANKING_LOCK="$RANKING_OUT/.runner.lock"
    if ! mkdir -- "$RANKING_LOCK" 2>/dev/null; then
      RANKING_OWNER="$(cat "$RANKING_LOCK/pid" 2>/dev/null || true)"
      if [[ "$RANKING_OWNER" =~ ^[0-9]+$ ]] && ! kill -0 "$RANKING_OWNER" 2>/dev/null; then
        rm -- "$RANKING_LOCK/pid"
        rmdir -- "$RANKING_LOCK"
        mkdir -- "$RANKING_LOCK" || { printf '%s\n' 'Another ranking runner acquired the preset.' >&2; exit 2; }
      else
        printf '%s\n' 'This ranking preset is already locked by another runner.' >&2
        exit 2
      fi
    fi
    printf '%s\n' "$$" > "$RANKING_LOCK/pid"
    RANKING_CHILD=""
    ranking_cleanup() {
      if [[ -n "$RANKING_CHILD" ]] && kill -0 "$RANKING_CHILD" 2>/dev/null; then
        kill -TERM "$RANKING_CHILD" 2>/dev/null || true
        wait "$RANKING_CHILD" 2>/dev/null || true
      fi
      rm -- "$RANKING_LOCK/pid"
      rmdir -- "$RANKING_LOCK"
    }
    trap ranking_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    RANKING_RUNTIME_MANIFEST="$RANKING_OUT/manifest.runtime.json"
    RANKING_LAB="$RANKING_OUT/lab.json"
    RANKING_LAB_CACHE="$RANKING_OUT/lab-cache"
    RANKING_GUIDE="$RANKING_OUT/lab-with-synergies.json"
    RANKING_PLAN="$RANKING_OUT/plan.json"
    RANKING_CACHE="$RANKING_OUT/cache"
    RANKING_RESULTS="$RANKING_OUT/results.json"
    RANKING_LOG="$RANKING_OUT/runner.log"
    RANKING_THREADS="$(python3 - "$RANKING_MANIFEST" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['threads'])
PY
)"
    RANKING_LAB_SECONDS=60
    [[ "$RANKING_PRESET" == smoke ]] && RANKING_LAB_SECONDS=15
    RANKING_FP="$("$TASK_BINARY" fingerprint)"
    python3 - "$RANKING_MANIFEST" "$RANKING_RUNTIME_MANIFEST" "$RANKING_FP" <<'PY'
import json, sys
manifest=json.load(open(sys.argv[1])); manifest['engineFingerprint']=sys.argv[3]
with open(sys.argv[2], 'w') as f: json.dump(manifest, f, indent=2); f.write('\n')
PY
    RANKING_MOVES="$(python3 - "$TASK_REPO_DIR/simulator/data/game.json" <<'PY'
import json,sys
game=json.load(open(sys.argv[1]))
print(','.join(sorted(k for k,v in game['moves'].items() if v.get('kind') != 'buff')))
PY
)"
    RANKING_MOVE_COUNT="$(awk -F, '{print NF}' <<< "$RANKING_MOVES")"
    RANKING_LAB_TASKS="$((RANKING_MOVE_COUNT * 7 * 2 * 2))"
    if (( RANKING_DRY )); then
      printf '%s\n' 'Dry run: no simulations will start.'
      printf 'Attack lab upper task estimate: %s moves x 7 scenarios x 2 levels x 2 seeds = %s.\n' "$RANKING_MOVE_COUNT" "$RANKING_LAB_TASKS"
      if [[ -f "$RANKING_LAB" ]] && python3 - "$RANKING_LAB" "$RANKING_FP" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1])); raise SystemExit(0 if d.get('complete') is True and d.get('partialScope') is not True and d.get('scope') == 'all-supported-attacks' and d.get('engineFingerprint')==sys.argv[2] else 1)
except Exception: raise SystemExit(1)
PY
      then
        "$TASK_BINARY" ranking plan "$RANKING_RUNTIME_MANIFEST" "$RANKING_LAB" "$RANKING_PLAN"
        python3 - "$RANKING_PLAN" <<'PY'
import json,sys
c=json.load(open(sys.argv[1])).get('counts',{})
print(f"Ranking plan upper bound: {c.get('matchesUpperBound', 'unavailable')} tasks (existing lab artifact).")
PY
      else
        RANKING_DEXES="$(python3 - "$RANKING_MANIFEST" "$TASK_REPO_DIR/simulator/data/game.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); g=json.load(open(sys.argv[2]))
print(len(g['dex']) if m['dex']=='all' else len(m['dex']))
PY
)"
        printf 'Ranking analytic upper estimate: %s species x 4 style/TM strata x [12xA2 + 3xB8 + 1xD16 candidates + 1x(A2+B8+D16) stock control] = %s tasks.\n' "$RANKING_DEXES" "$((RANKING_DEXES * 4 * 90))"
      fi
      printf '%s\n' 'Task counts are upper estimates; runtime and cost are unmeasured.'
      exit 0
    fi
    run_monitored() {
      local label="$1"; shift
      local start="$SECONDS" last=0 status=0
      printf '[%s] starting %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label" | tee -a "$RANKING_LOG"
      "$@" >>"$RANKING_LOG" 2>&1 & RANKING_CHILD=$!
      while kill -0 "$RANKING_CHILD" 2>/dev/null; do
        sleep 1
        if (( SECONDS - last >= 60 )); then
          printf '[%s] heartbeat %s; elapsed %ss; log=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$label" "$((SECONDS - start))" "$RANKING_LOG" | tee -a "$RANKING_LOG" >&2
          for progress in "$RANKING_RESULTS.progress.json"; do
            if [[ -f "$progress" ]]; then
              python3 - "$progress" <<'PY' >&2 || true
import json,sys
try:
 d=json.load(open(sys.argv[1])); print(f"progress: stage={d.get('stage')} completed_configuration_runs={d.get('completedConfigurationRuns')} elapsed={d.get('elapsedWallSeconds')}s")
except Exception: print(f"progress {sys.argv[1]}: artifact not readable yet")
PY
            fi
          done
          last="$SECONDS"
        fi
      done
      wait "$RANKING_CHILD" || status=$?
      RANKING_CHILD=""
      return "$status"
    }
    run_monitored attack-lab "$TASK_BINARY" attack-lab run "$RANKING_LAB" "$RANKING_LAB_CACHE" "$RANKING_THREADS" "$RANKING_LAB_SECONDS" "$RANKING_MOVES"
    python3 - "$RANKING_LAB" "$RANKING_FP" <<'PY'
import json,sys
lab=json.load(open(sys.argv[1]))
if lab.get('complete') is not True or lab.get('partialScope') is True or lab.get('scope') != 'all-supported-attacks' or lab.get('engineFingerprint') != sys.argv[2]:
    raise SystemExit('ranking requires a complete, current-fingerprint all-supported-attacks lab artifact')
PY
    run_monitored synergy-lab "$TASK_BINARY" synergy-lab run "$RANKING_LAB" "$RANKING_GUIDE" "$RANKING_OUT/synergy-cache" "$RANKING_THREADS" "$RANKING_LAB_SECONDS"
    "$TASK_BINARY" ranking plan "$RANKING_RUNTIME_MANIFEST" "$RANKING_GUIDE" "$RANKING_PLAN"
    RANKING_ACTION=run
    [[ -f "$RANKING_RESULTS" ]] && RANKING_ACTION=resume
    run_monitored "ranking-$RANKING_ACTION" "$TASK_BINARY" ranking "$RANKING_ACTION" "$RANKING_PLAN" "$RANKING_CACHE" "$RANKING_RESULTS"
    POKESIM_ATTACK_LAB="$RANKING_OUT/attacks.json" PYTHONPATH="$TASK_REPO_DIR" python3 -m build.laboratory_export "$RANKING_LAB" "$RANKING_RESULTS" "$TASK_REPO_DIR/simulator/data/game.json" "$RANKING_OUT/attacks.json" "$RANKING_OUT/sim-results.json"
    printf '%s\n' "Ranking $RANKING_PRESET finished. Results: $RANKING_OUT. Duration is not yet measured on Runpod; results are diagnostic and not a global optimum."
    ;;
  funnel)
    printf '%s\n' 'The exhaustive funnel path is retired. Migrate to: bash simulator/runpod/run.sh ranking smoke|full [--dry-run]. Explicit legacy production commands remain available.' >&2
    exit 2
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
      'Usage: bash simulator/runpod/run.sh prepare|plan|benchmark|cost|run|resume|ranking|funnel' \
      'prepare: compile and test only; plan: write a finite ledger without matches.' \
      'benchmark: bounded mature scenes only; run/resume: explicit production execution.' \
      'ranking smoke|full [--dry-run]: bounded lab plus ranking; dry-run reports task-count estimates only.' \
      'funnel: retired; use ranking smoke|full.' \
      'Cloud compute is not released automatically: save results, then terminate your pod.'
    ;;
esac
